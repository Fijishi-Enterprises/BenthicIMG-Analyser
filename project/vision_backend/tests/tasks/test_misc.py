from unittest import mock

from django.test.utils import patch_logger
from django.urls import reverse

from annotations.models import Annotation
from images.models import Image
from jobs.models import Job
from jobs.tasks import run_scheduled_jobs_until_empty
from jobs.utils import queue_job
from lib.tests.utils import BaseTest
from ...models import Score, Classifier
from ...tasks import collect_spacer_jobs
from .utils import BaseTaskTest


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
        queue_job(
            'reset_classifiers_for_source', self.source.pk,
            source_id=self.source.pk)
        run_scheduled_jobs_until_empty()

        # Verify that classifier-related objects were cleared, but not features

        with self.assertRaises(Classifier.DoesNotExist):
            Classifier.objects.get(
                pk=classifier_id, msg="Classifier should be deleted")

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
        queue_job(
            'reset_backend_for_source', self.source.pk,
            source_id=self.source.pk)
        run_scheduled_jobs_until_empty()

        # Verify that backend objects were cleared

        with self.assertRaises(Classifier.DoesNotExist):
            Classifier.objects.get(
                pk=classifier_id, msg="Classifier should be deleted")

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


def call_collect_spacer_jobs():
    collect_spacer_jobs()

    class Queue:
        status_counts = dict()
        def collect_jobs(self):
            return []
    return Queue


class CollectSpacerJobsTest(BaseTest):

    def test_no_multiple_runs(self):
        """
        Should block multiple existing runs of this task. That way, no spacer
        job can get collected multiple times.
        """
        with patch_logger('jobs.utils', 'debug') as log_messages:

            # Mock a function called by the task, and make that function
            # attempt to run the task recursively.
            with mock.patch(
                'vision_backend.tasks.get_queue_class', call_collect_spacer_jobs
            ):
                collect_spacer_jobs()

            log_message = (
                "Job [collect_spacer_jobs / ]"
                " is already pending or in progress."
            )
            self.assertIn(
                log_message, log_messages,
                "Should log the appropriate message")

        self.assertEqual(
            Job.objects.filter(job_name='collect_spacer_jobs').count(), 1,
            "Should not have accepted the second run")
