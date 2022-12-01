from datetime import timedelta

from django.core import mail
from django.urls import reverse
from django.utils import timezone

from annotations.models import Annotation
from images.models import Image
from jobs.tasks import run_scheduled_jobs_until_empty
from lib.tests.utils import BaseTest, ClientTest
from vision_backend.models import BatchJob, Score, Classifier
import vision_backend.task_helpers as th
from vision_backend.tasks import (
    clean_up_old_batch_jobs, collect_spacer_jobs, reset_backend_for_source,
    reset_classifiers_for_source, warn_about_stuck_jobs)
from vision_backend.tests.tasks.utils import BaseTaskTest


class TestJobTokenEncode(BaseTest):

    def test_encode_one(self):

        job_token = th.encode_spacer_job_token([4])
        self.assertIn('4', job_token)

    def test_encode_three(self):
        job_token = th.encode_spacer_job_token([4, 5, 6])
        self.assertIn('4', job_token)
        self.assertIn('5', job_token)
        self.assertIn('6', job_token)

    def test_round_trip(self):
        pks_in = [4, 5, 6]
        job_token = th.encode_spacer_job_token(pks_in)
        pks_out = th.decode_spacer_job_token(job_token)
        self.assertEqual(pks_in, pks_out)


class ResetTaskTest(BaseTaskTest):

    def test_reset_classifiers_for_source(self):

        # Classify image and verify that it worked

        self.upload_data_and_train_classifier()
        img = self.upload_image_and_machine_classify(self.user, self.source)

        classifier = self.source.get_latest_robot()
        self.assertIsNotNone(classifier, "Should have a classifier")
        classifier_id = classifier.pk

        self.assertTrue(img.features.extracted, "img should have features")
        self.assertTrue(img.features.classified, "img should be classified")
        self.assertGreater(
            Score.objects.filter(image=img).count(), 0,
            "img should have scores")
        self.assertGreater(
            Annotation.objects.filter(image=img).count(), 0,
            "img should have annotations")

        # Reset classifiers
        reset_classifiers_for_source(self.source.pk)

        # Verify that classifier-related objects were cleared, but not features

        self.assertRaises(
            Classifier.DoesNotExist,
            callableObj=Classifier.objects.get, pk=classifier_id,
            msg="Classifier should be deleted")

        img.features.refresh_from_db()
        self.assertTrue(img.features.extracted, "img SHOULD have features")
        self.assertFalse(img.features.classified, "img shouldn't be classified")
        self.assertEqual(
            Score.objects.filter(image=img).count(), 0,
            "img shouldn't have scores")
        self.assertEqual(
            Annotation.objects.filter(image=img).count(), 0,
            "img shouldn't have annotations")

        # Train
        run_scheduled_jobs_until_empty()
        collect_spacer_jobs()
        # Classify
        run_scheduled_jobs_until_empty()

        img.features.refresh_from_db()
        self.assertTrue(img.features.classified, "img should be classified")
        self.assertGreater(
            Score.objects.filter(image=img).count(), 0,
            "img should have scores")
        self.assertGreater(
            Annotation.objects.filter(image=img).count(), 0,
            "img should have annotations")

        # Ensure confirmed annotations weren't deleted
        for image in self.source.image_set.exclude(pk=img.pk):
            self.assertTrue(
                image.annotation_set.confirmed().exists(),
                "Confirmed annotations should still exist")
            self.assertTrue(
                image.annoinfo.confirmed,
                "Confirmed image should still be confirmed")

    def test_reset_backend_for_source(self):

        # Classify image and verify that it worked

        self.upload_data_and_train_classifier()
        img = self.upload_image_and_machine_classify(self.user, self.source)

        classifier = self.source.get_latest_robot()
        self.assertIsNotNone(classifier, "Should have a classifier")
        classifier_id = classifier.pk

        self.assertTrue(img.features.extracted, "img should have features")
        self.assertTrue(img.features.classified, "img should be classified")
        self.assertGreater(
            Score.objects.filter(image=img).count(), 0,
            "img should have scores")
        self.assertGreater(
            Annotation.objects.filter(image=img).count(), 0,
            "img should have annotations")

        # Reset backend
        reset_backend_for_source(self.source.pk)

        # Verify that backend objects were cleared

        self.assertRaises(
            Classifier.DoesNotExist,
            callableObj=Classifier.objects.get, pk=classifier_id,
            msg="Classifier should be deleted")

        img.features.refresh_from_db()
        self.assertFalse(img.features.extracted, "img shouldn't have features")
        self.assertFalse(img.features.classified, "img shouldn't be classified")
        self.assertEqual(
            Score.objects.filter(image=img).count(), 0,
            "img shouldn't have scores")
        self.assertEqual(
            Annotation.objects.filter(image=img).count(), 0,
            "img shouldn't have annotations")

        # Extract features
        run_scheduled_jobs_until_empty()
        collect_spacer_jobs()
        # Train
        run_scheduled_jobs_until_empty()
        collect_spacer_jobs()
        # Classify
        run_scheduled_jobs_until_empty()

        img.features.refresh_from_db()
        self.assertTrue(img.features.extracted, "img should have features")
        self.assertTrue(img.features.classified, "img should be classified")
        self.assertGreater(
            Score.objects.filter(image=img).count(), 0,
            "img should have scores")
        self.assertGreater(
            Annotation.objects.filter(image=img).count(), 0,
            "img should have annotations")

        # Ensure confirmed annotations weren't deleted
        for image in self.source.image_set.exclude(pk=img.pk):
            self.assertTrue(
                image.annotation_set.confirmed().exists(),
                "Confirmed annotations should still exist")
            self.assertTrue(
                image.annoinfo.confirmed,
                "Confirmed image should still be confirmed")

    def test_point_change_cleanup(self):
        """
        If we generate new points, features must be reset.
        """
        img = self.upload_image(self.user, self.source)
        img.features.extracted = True
        img.features.classified = True
        img.features.save()

        self.assertTrue(Image.objects.get(id=img.id).features.extracted)
        self.assertTrue(Image.objects.get(id=img.id).features.classified)

        self.client.force_login(self.user)
        url = reverse('image_regenerate_points', args=[img.id])
        self.client.post(url)

        # Now features should be reset
        self.assertFalse(Image.objects.get(id=img.id).features.extracted)
        self.assertFalse(Image.objects.get(id=img.id).features.classified)


class BatchJobCleanupTest(ClientTest):
    """
    Test cleanup of old AWS Batch jobs.
    """
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()

        cls.user = cls.create_user()

    def test_job_selection(self):
        """
        Only jobs eligible for cleanup should be cleaned up.
        """
        # More than one job too new to be cleaned up.

        job = BatchJob(job_token='new')
        job.save()

        job = BatchJob(job_token='29 days ago')
        job.save()
        job.create_date = timezone.now() - timedelta(days=29)
        job.save()

        # More than one job old enough to be cleaned up.

        job = BatchJob(job_token='31 days ago')
        job.save()
        job.create_date = timezone.now() - timedelta(days=31)
        job.save()

        job = BatchJob(job_token='32 days ago')
        job.save()
        job.create_date = timezone.now() - timedelta(days=32)
        job.save()

        clean_up_old_batch_jobs()

        self.assertTrue(
            BatchJob.objects.filter(job_token='new').exists(),
            "Shouldn't clean up new job")
        self.assertTrue(
            BatchJob.objects.filter(job_token='29 days ago').exists(),
            "Shouldn't clean up 29 day old job")
        self.assertFalse(
            BatchJob.objects.filter(job_token='31 days ago').exists(),
            "Should clean up 31 day old job")
        self.assertFalse(
            BatchJob.objects.filter(job_token='32 days ago').exists(),
            "Should clean up 32 day old job")


class WarnAboutStuckJobsTest(ClientTest):
    """
    Test warning about AWS Batch jobs that haven't completed in a timely
    fashion.
    """
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()

        cls.user = cls.create_user()

    def test_job_selection_by_date(self):
        """
        Only warn about jobs between 5 and 6 days old, and warn once per job.
        """
        job1 = BatchJob.objects.create(job_token='1', batch_token='4d 23h ago')
        job1.create_date = timezone.now() - timedelta(days=4, hours=23)
        job1.save()

        job2 = BatchJob.objects.create(job_token='2', batch_token='5d 1h ago')
        job2.create_date = timezone.now() - timedelta(days=5, hours=1)
        job2.save()

        job3 = BatchJob.objects.create(job_token='3', batch_token='5d 23h ago')
        job3.create_date = timezone.now() - timedelta(days=5, hours=23)
        job3.save()

        job4 = BatchJob.objects.create(job_token='4', batch_token='6d 1h ago')
        job4.create_date = timezone.now() - timedelta(days=6, hours=1)
        job4.save()

        warn_about_stuck_jobs()

        self.assertEqual(len(mail.outbox), 1)
        sent_email = mail.outbox[0]

        self.assertEqual(
            "[CoralNet] 2 AWS Batch job(s) not completed after 5 days",
            sent_email.subject)
        self.assertEqual(
            "The following AWS Batch jobs were not completed after 5 days:"
            "\n"
            f"\nBatch token: 5d 1h ago, job token: 2, job id: {job2.pk}"
            f"\nBatch token: 5d 23h ago, job token: 3, job id: {job3.pk}",
            sent_email.body)

    def test_job_selection_by_status(self):
        """
        Only warn about non-completed jobs.
        """
        job1 = BatchJob.objects.create(
            job_token='1', batch_token='PENDING', status='PENDING')
        job1.create_date = timezone.now() - timedelta(days=5, hours=1)
        job1.save()

        job2 = BatchJob.objects.create(
            job_token='2', batch_token='SUCCEEDED', status='SUCCEEDED')
        job2.create_date = timezone.now() - timedelta(days=5, hours=1)
        job2.save()

        job3 = BatchJob.objects.create(
            job_token='3', batch_token='RUNNING', status='RUNNING')
        job3.create_date = timezone.now() - timedelta(days=5, hours=1)
        job3.save()

        job4 = BatchJob.objects.create(
            job_token='4', batch_token='FAILED', status='FAILED')
        job4.create_date = timezone.now() - timedelta(days=5, hours=1)
        job4.save()

        warn_about_stuck_jobs()

        self.assertEqual(len(mail.outbox), 1)
        sent_email = mail.outbox[0]

        self.assertEqual(
            "[CoralNet] 2 AWS Batch job(s) not completed after 5 days",
            sent_email.subject)
        self.assertEqual(
            "The following AWS Batch jobs were not completed after 5 days:"
            "\n"
            f"\nBatch token: PENDING, job token: 1, job id: {job1.pk}"
            f"\nBatch token: RUNNING, job token: 3, job id: {job3.pk}",
            sent_email.body)
