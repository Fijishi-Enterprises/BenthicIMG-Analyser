from datetime import timedelta
import mock

import numpy as np
from django.core.urlresolvers import reverse
from django.test import override_settings
from django.conf import settings
from django.utils import timezone
import spacer.config as spacer_config
from spacer.data_classes import ImageFeatures, ValResults
from spacer.messages import ClassifyReturnMsg

import vision_backend.task_helpers as th
from accounts.utils import is_robot_user
from annotations.models import Annotation
from images.model_utils import PointGen
from images.models import Image, Point
from django.core.files.storage import get_storage_class
from lib.tests.utils import BaseTest, ClientTest
from upload.tests.utils import UploadAnnotationsTestMixin
from vision_backend.models import BatchJob, Score, Classifier
from vision_backend.tasks import \
    classify_image, \
    clean_up_old_batch_jobs, \
    collect_all_jobs, \
    reset_after_labelset_change, \
    submit_classifier


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


class MockImage:
    # Prevent IDE warning about unresolved attribute.
    metadata = None

    @property
    def valset(self):
        """
        It can be tricky to assert on train set / validation set when it's
        based on image primary key. Make it based on the image name
        instead. If name starts with 'val', it's in val set. Else, it's in
        train set.
        """
        return self.metadata.name.startswith('val')


# Note that spacer also has its own minimum image count for training.
@override_settings(MIN_NBR_ANNOTATED_IMAGES=1)
@override_settings(SPACER_QUEUE_CHOICE='vision_backend.queues.LocalQueue')
class BaseTaskTest(ClientTest, UploadAnnotationsTestMixin):
    """Base test class for testing the backend's 'main' tasks."""

    @classmethod
    def setUpTestData(cls):
        super(BaseTaskTest, cls).setUpTestData()

        cls.user = cls.create_user()
        cls.source = cls.create_source(
            cls.user,
            point_generation_type=PointGen.Types.SIMPLE,
            simple_number_of_points=5)
        cls.labels = cls.create_labels(cls.user, ['A', 'B'], "Group1")
        cls.create_labelset(cls.user, cls.source, cls.labels)

    def assertExistsInStorage(self, filepath):
        storage = get_storage_class()()
        self.assertTrue(storage.exists(filepath))

    def upload_image_with_annotations(self, filename):
        img = self.upload_image(
            self.user, self.source, image_options=dict(filename=filename))
        self.add_annotations(
            self.user, img, {1: 'A', 2: 'B', 3: 'A', 4: 'A', 5: 'B'})
        return img

    def upload_images_for_training(self, train_image_count, val_image_count):
        for _ in range(train_image_count):
            self.upload_image_with_annotations(
                'train{}.png'.format(self.image_count))
        for _ in range(val_image_count):
            self.upload_image_with_annotations(
                'val{}.png'.format(self.image_count))

    def upload_image_with_dupe_points(self, filename, with_labels=False):
        img = self.upload_image(
            self.user, self.source, image_options=dict(filename=filename))

        # Upload points, including a duplicate.
        if with_labels:
            rows = [
                ['Name', 'Row', 'Column', 'Label'],
                [filename, 50, 50, 'A'],
                [filename, 40, 60, 'B'],
                [filename, 50, 50, 'A'],
            ]
        else:
            rows = [
                ['Name', 'Row', 'Column'],
                [filename, 50, 50],
                [filename, 40, 60],
                [filename, 50, 50],
            ]
        csv_file = self.make_csv_file('A.csv', rows)
        self.preview_csv_annotations(
            self.user, self.source, csv_file)
        self.upload_annotations(self.user, self.source)

        img.refresh_from_db()
        self.assertEqual(
            PointGen.args_to_db_format(
                point_generation_type=PointGen.Types.IMPORTED,
                imported_number_of_points=3),
            img.point_generation_method,
            "Points should be saved successfully")

        return img

    rowcols_with_dupes_included = [(40, 60), (50, 50), (50, 50)]
    rowcols_with_dupes_removed = [(40, 60), (50, 50)]


class ExtractFeaturesTest(BaseTaskTest):

    def test_success(self):
        # After an image upload, features are ready to be submitted.
        img = self.upload_image(self.user, self.source)

        self.assertExistsInStorage(
            settings.FEATURE_VECTOR_FILE_PATTERN.format(
                full_image_path=img.original_file.name))

        # With LocalQueue, the result should be
        # available for collection immediately.
        collect_all_jobs()

        # Features should be successfully extracted.
        self.assertTrue(img.features.extracted)

    def test_with_dupe_points(self):
        """
        The image to have features extracted has two points with the same
        row/column.
        """

        # Upload.
        img = self.upload_image_with_dupe_points('1.png')
        # Process feature extraction result.
        collect_all_jobs()

        self.assertTrue(img.features.extracted, "Features should be extracted")

        # Ensure the features are of the uploaded points, without dupes.
        storage = get_storage_class()()
        feature_loc = storage.spacer_data_loc(
            settings.FEATURE_VECTOR_FILE_PATTERN.format(
                full_image_path=img.original_file.name))
        features = ImageFeatures.load(feature_loc)
        rowcols = [(f.row, f.col) for f in features.point_features]
        self.assertListEqual(
            self.rowcols_with_dupes_removed, sorted(rowcols),
            "Feature rowcols should match the actual points, without dupes")


# Note: applying this patch decorator to the base class doesn't seem to work
# for some reason (the patch doesn't end up affecting the subclass).
@mock.patch('images.models.Image.valset', MockImage.valset)
class TrainClassifierTest(BaseTaskTest):

    def test_success(self):
        # Provide enough data for training, and extract features.
        self.upload_images_for_training(
            train_image_count=spacer_config.MIN_TRAINIMAGES, val_image_count=1)
        collect_all_jobs()

        # Create a classifier
        job_msg = submit_classifier(self.source.id)

        # This source should now have a classifier (though not trained yet)
        self.assertTrue(
            Classifier.objects.filter(source=self.source).count() > 0)

        # Process training result
        collect_all_jobs()

        # Now we should have a trained classifier whose accuracy is the best so
        # far (due to having no previous classifiers), and thus it should have
        # been marked as valid
        latest_classifier = self.source.get_latest_robot()
        self.assertTrue(latest_classifier.valid)

        # Also check that the actual classifier is created in storage.
        storage = get_storage_class()()
        self.assertTrue(storage.exists(
            settings.ROBOT_MODEL_FILE_PATTERN.format(pk=latest_classifier.pk)))

        # And that the val results are stored.
        self.assertTrue(storage.exists(
            settings.ROBOT_MODEL_VALRESULT_PATTERN.format(
                pk=latest_classifier.pk)))

        # Check that the point-counts in val_res is equal to val_data.
        val_res = ValResults.load(job_msg.tasks[0].valresult_loc)
        val_labels = job_msg.tasks[0].val_labels
        self.assertEqual(len(val_res.gt),
                         len(val_labels) * val_labels.samples_per_image)

    def test_with_dupe_points(self):
        """
        Images in the training set and validation set have two points with the
        same row/column.
        """

        # Upload annotated images with dupe points
        val_image_with_dupe_point = self.upload_image_with_dupe_points(
            'val.png', with_labels=True)
        training_image_with_dupe_point = self.upload_image_with_dupe_points(
            'train.png', with_labels=True)
        # Other annotated images to get enough for training
        self.upload_images_for_training(
            train_image_count=spacer_config.MIN_TRAINIMAGES-1,
            val_image_count=0)

        # Process feature extraction results
        collect_all_jobs()

        # Train classifier
        job_msg = submit_classifier(self.source.id)
        collect_all_jobs()

        # Check training data

        storage = get_storage_class()()
        train_data = job_msg.tasks[0].train_labels.data
        feature_filepath = settings.FEATURE_VECTOR_FILE_PATTERN.format(
            full_image_path=training_image_with_dupe_point.original_file.name)
        feature_location = storage.spacer_data_loc(feature_filepath)
        image_train_data = train_data[feature_location.key]
        self.assertEqual(
            len(self.rowcols_with_dupes_included), len(image_train_data),
            "Training data count should include dupe points")
        rowcols = [
            (row, col) for row, col, label in image_train_data]
        self.assertListEqual(
            self.rowcols_with_dupes_included, sorted(rowcols),
            "Training data rowcols should include dupe points")

        # Check validation data

        val_data = job_msg.tasks[0].val_labels.data
        feature_filepath = settings.FEATURE_VECTOR_FILE_PATTERN.format(
            full_image_path=val_image_with_dupe_point.original_file.name)
        feature_location = storage.spacer_data_loc(feature_filepath)
        image_val_data = val_data[feature_location.key]
        self.assertEqual(
            len(self.rowcols_with_dupes_included), len(image_val_data),
            "Validation data count should include dupe points")
        rowcols = [
            (row, col) for row, col, label in image_val_data]
        self.assertListEqual(
            self.rowcols_with_dupes_included, sorted(rowcols),
            "Validation data rowcols should include dupe points")

        # Check valresults

        val_res = ValResults.load(job_msg.tasks[0].valresult_loc)
        self.assertEqual(
            len(self.rowcols_with_dupes_included), len(val_res.gt),
            "Valresults count should include dupe points")

        # Check that there's a valid classifier.

        latest_classifier = self.source.get_latest_robot()
        self.assertTrue(latest_classifier.valid)


@mock.patch('images.models.Image.valset', MockImage.valset)
class ClassifyImageTest(BaseTaskTest):

    def train_classifier(self):
        # Provide enough data for training
        self.upload_images_for_training(
            train_image_count=spacer_config.MIN_TRAINIMAGES, val_image_count=1)
        # Process feature extraction results
        collect_all_jobs()

        # Train classifier
        submit_classifier(self.source.id)
        collect_all_jobs()

    def test_classify_unannotated_image(self):
        """Classify an image where all points are unannotated."""
        self.train_classifier()

        # Image without annotations
        img = self.upload_image(self.user, self.source)
        # Process feature extraction results + classify image
        collect_all_jobs()

        for point in Point.objects.filter(image__id=img.id):
            self.assertTrue(
                point.annotation is not None,
                "New image's points should be classified")
            self.assertTrue(
                is_robot_user(point.annotation.user),
                "Image should have robot annotations")
            # Score count per point should be label count or 5,
            # whichever is less. (In this case it's label count)
            self.assertEqual(
                2, point.score_set.count(), "Each point should have scores")

    def test_more_than_5_labels(self):
        """
        When there are more than 5 labels, score count should be capped to 5.
        """
        # Increase label count from 2 to 8.
        labels = self.create_labels(
            self.user, ['C', 'D', 'E', 'F', 'G', 'H'], "Group2")
        self.create_labelset(self.user, self.source, labels | self.labels)

        # Use each label, so that they all have enough training
        # data to be considered during classification.
        img = self.upload_image(self.user, self.source)
        self.add_annotations(
            self.user, img, {1: 'A', 2: 'B', 3: 'C', 4: 'D', 5: 'E'})
        img = self.upload_image(self.user, self.source)
        self.add_annotations(
            self.user, img, {1: 'F', 2: 'G', 3: 'H', 4: 'B', 5: 'C'})
        img = self.upload_image(self.user, self.source)
        self.add_annotations(
            self.user, img, {1: 'D', 2: 'E', 3: 'F', 4: 'G', 5: 'H'})

        # This uploads a bunch of images using nothing but A/B, then runs
        # tasks needed to train a classifier.
        self.train_classifier()

        # Upload, extract features, classify
        img = self.upload_image(self.user, self.source)
        collect_all_jobs()

        for point in Point.objects.filter(image__id=img.id):
            # Score count per point should be label count or 5,
            # whichever is less. (In this case it's 5)
            self.assertEqual(
                5, point.score_set.count(), "Each point should have 5 scores")

    def test_classify_unconfirmed_image(self):
        """
        Classify an image which has already been machine-classified
        previously.
        """
        def mock_classify_msg_1(
                self_, runtime, scores, classes, valid_rowcol):
            self_.runtime = runtime
            self_.classes = classes
            self_.valid_rowcol = valid_rowcol

            # 1 list per point; 1 float score per label per point.
            # This would classify as all A.
            scores_simple = [
                [0.8, 0.2], [0.8, 0.2], [0.8, 0.2], [0.8, 0.2], [0.8, 0.2],
            ]
            self_.scores = []
            for i, score in enumerate(scores):
                self_.scores.append((score[0], score[1], scores_simple[i]))

        def mock_classify_msg_2(
                self_, runtime, scores, classes, valid_rowcol):
            self_.runtime = runtime
            self_.classes = classes
            self_.valid_rowcol = valid_rowcol

            # This would classify as 3 A's, 2 B's.
            # We'll just check the count of each label later to check
            # correctness of results, since assigning specific scores to
            # specific points is trickier to keep track of.
            scores_simple = [
                [0.6, 0.4], [0.4, 0.6], [0.4, 0.6], [0.6, 0.4], [0.6, 0.4],
            ]
            self_.scores = []
            for i, score in enumerate(scores):
                self_.scores.append((score[0], score[1], scores_simple[i]))

        self.train_classifier()
        clf_1 = self.source.get_latest_robot()

        # Upload
        img = self.upload_image(self.user, self.source)
        # Extract features + classify with a particular set of scores
        with mock.patch(
                'spacer.messages.ClassifyReturnMsg.__init__',
                mock_classify_msg_1):
            collect_all_jobs()

        # Create another valid classifier. Override settings so that 1) we
        # don't need more images to train a new classifier, and 2) we don't
        # need improvement to mark a new classifier as valid.
        with override_settings(
                NEW_CLASSIFIER_TRAIN_TH=0.0001,
                NEW_CLASSIFIER_IMPROVEMENT_TH=0.0001):
            submit_classifier(self.source.id)
            # 1) Save classifier. 2) re-classify with a different set of
            # scores so that specific points get their labels changed (and
            # other points don't).
            with mock.patch(
                    'spacer.messages.ClassifyReturnMsg.__init__',
                    mock_classify_msg_2):
                collect_all_jobs()

        clf_2 = self.source.get_latest_robot()
        self.assertNotEqual(
            clf_1.id, clf_2.id, "Should have a new valid classifier")

        for point in Point.objects.filter(image=img):
            self.assertTrue(
                is_robot_user(point.annotation.user),
                "Should still have robot annotations")
        self.assertEqual(
            3,
            Point.objects.filter(
                image=img, annotation__label__name='A').count(),
            "3 points should be labeled A")
        self.assertEqual(
            2,
            Point.objects.filter(
                image=img, annotation__label__name='B').count(),
            "2 points should be labeled B")
        self.assertEqual(
            3,
            Point.objects.filter(
                image=img, annotation__robot_version=clf_1).count(),
            "3 points should still be under classifier 1")
        self.assertEqual(
            2,
            Point.objects.filter(
                image=img, annotation__robot_version=clf_2).count(),
            "2 points should have been updated by classifier 2")

    def test_classify_partially_confirmed_image(self):
        """
        Classify an image where some, but not all points have confirmed
        annotations.
        """
        self.train_classifier()

        # Image without annotations
        img = self.upload_image(self.user, self.source)
        # Add partial annotations
        self.add_annotations(self.user, img, {1: 'A'})
        # Process feature extraction results + classify image
        collect_all_jobs()

        for point in Point.objects.filter(image__id=img.id):
            if point.point_number == 1:
                self.assertFalse(
                    is_robot_user(point.annotation.user),
                    "The confirmed annotation should still be confirmed")
            else:
                self.assertTrue(
                    is_robot_user(point.annotation.user),
                    "The other annotations should be unconfirmed")
            self.assertEqual(
                2, point.score_set.count(), "Each point should have scores")

    def test_classify_confirmed_image(self):
        """Attempt to classify an image where all points are confirmed."""
        self.train_classifier()

        # Image with annotations
        img = self.upload_image_with_annotations('confirmed.png')
        # Process feature extraction results
        collect_all_jobs()
        # Try to classify
        classify_image(img.id)

        for point in Point.objects.filter(image__id=img.id):
            self.assertFalse(
                is_robot_user(point.annotation.user),
                "Image should still have confirmed annotations")
            self.assertEqual(
                2, point.score_set.count(), "Each point should have scores")

    def test_classify_scores_and_labels_match(self):
        """
        Check that the Scores and the labels assigned by classification are
        consistent with each other.
        """
        self.train_classifier()

        # Upload, extract features, classify
        img = self.upload_image(self.user, self.source)
        collect_all_jobs()

        for point in Point.objects.filter(image__id=img.id):
            ann = point.annotation
            scores = Score.objects.filter(point=point)
            posteriors = [score.score for score in scores]
            self.assertEqual(
                scores[int(np.argmax(posteriors))].label, ann.label,
                "Max score label should match the annotation label."
                " Posteriors: {}".format(posteriors))

    def test_with_dupe_points(self):
        """
        The image to be classified has two points with the same row/column.
        """
        # Provide enough data for training
        self.upload_images_for_training(
            train_image_count=spacer_config.MIN_TRAINIMAGES, val_image_count=1)
        # Add one image without annotations, including a duplicate point
        img = self.upload_image_with_dupe_points('has_dupe.png')
        # Extract features
        collect_all_jobs()

        # Train classifier + classify image
        submit_classifier(self.source.id)
        collect_all_jobs()

        self.assertEqual(
            len(self.rowcols_with_dupes_included),
            Annotation.objects.filter(image__id=img.id).count(),
            "New image should be classified, including dupe points")


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
