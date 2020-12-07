from datetime import timedelta

from django.core.urlresolvers import reverse
from django.test import override_settings
from django.utils import timezone
import numpy as np
from spacer.messages import ClassifyReturnMsg

from images.models import Image, Point
from lib.tests.utils import BaseTest, ClientTest
from vision_backend.models import BatchJob, Score, Classifier
import vision_backend.task_helpers as th
from vision_backend.tasks import (
    clean_up_old_batch_jobs, reset_after_labelset_change)


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


@override_settings(SPACER_QUEUE_CHOICE='vision_backend.queues.LocalQueue')
class ResetTaskTest(ClientTest):

    @classmethod
    def setUpTestData(cls):
        super(ResetTaskTest, cls).setUpTestData()

        cls.user = cls.create_user()
        cls.source = cls.create_source(cls.user)

        labels = cls.create_labels(cls.user,
                                   ['A', 'B', 'C', 'D', 'E', 'F', 'G'],
                                   "Group1")

        cls.create_labelset(cls.user, cls.source, labels.filter(
            name__in=['A', 'B', 'C', 'D', 'E', 'F', 'G'])
        )

    def test_labelset_change_cleanup(self):
        """
        If the labelset is changed, the whole backend must be reset.
        """

        # Create some dummy classifiers
        Classifier(source=self.source).save()
        Classifier(source=self.source).save()

        self.assertEqual(Classifier.objects.filter(
            source=self.source).count(), 2)

        # Create some dummy scores
        img = self.upload_image(self.user, self.source)

        # Pre-fetch label objects
        label_objs = self.source.labelset.get_globals()

        # Check number of points per image
        nbr_points = Point.objects.filter(image=img).count()

        # Fake creation of scores.
        scores = []
        for i in range(nbr_points):
            scores.append(np.random.rand(label_objs.count()))

        return_msg = ClassifyReturnMsg(
            runtime=0.0,
            scores=[(0, 0, [float(s) for s in scrs]) for scrs in scores],
            classes=[label.pk for label in label_objs],
            valid_rowcol=False,
        )

        th.add_scores(img.pk, return_msg, label_objs)

        expected_nbr_scores = min(5, label_objs.count())
        self.assertEqual(Score.objects.filter(image=img).count(),
                         nbr_points * expected_nbr_scores)

        # Fake that the image is classified
        img.features.classified = True
        img.features.save()
        self.assertTrue(Image.objects.get(id=img.id).features.classified)

        # Now, reset the source.
        reset_after_labelset_change(self.source.id)

        self.assertEqual(Classifier.objects.filter(
            source=self.source).count(), 0)
        self.assertEqual(Score.objects.filter(image=img).count(), 0)
        self.assertFalse(Image.objects.get(id=img.id).features.classified)

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
        super(BatchJobCleanupTest, cls).setUpTestData()

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
            "Shouldn't clean up 31 day old job")
        self.assertFalse(
            BatchJob.objects.filter(job_token='32 days ago').exists(),
            "Shouldn't clean up 32 day old job")
