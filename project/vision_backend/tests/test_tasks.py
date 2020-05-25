import numpy as np
from django.core.urlresolvers import reverse
from django.test import override_settings

import vision_backend.task_helpers as th
from accounts.utils import is_robot_user
from annotations.models import Annotation
from images.model_utils import PointGen
from images.models import Image, Point
from lib.tests.utils import ClientTest
from vision_backend.models import Score, Classifier
from vision_backend.tasks import \
    classify_image, \
    collect_all_jobs, \
    reset_after_labelset_change, \
    submit_classifier, \
    submit_features


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
        th._add_scores(img.pk, scores, label_objs)

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


class ClassifyUtilsTest(ClientTest):
    """Test helper/utility functions used by the classify-image task."""

    @classmethod
    def setUpTestData(cls):
        super(ClassifyUtilsTest, cls).setUpTestData()

        cls.user = cls.create_user()
        cls.points_per_image = 3
        cls.source = cls.create_source(
            cls.user,
            point_generation_type=PointGen.Types.SIMPLE,
            simple_number_of_points=cls.points_per_image,
        )

        cls.labels = cls.create_labels(
            cls.user, ['A', 'B', 'C', 'D'], "Group1")
        cls.create_labelset(cls.user, cls.source, cls.labels)
        # Make the order predictable so that we can specify scores easily
        cls.labels.order_by('default_code')

    @classmethod
    def classify(cls, img, classifier=None, scores=None):
        if not classifier:
            classifier = Classifier(source=cls.source, valid=True)
            classifier.save()
        if not scores:
            scores = [
                np.random.rand(cls.labels.count())
                for _ in range(cls.points_per_image)]
        th._add_scores(img.pk, scores, cls.labels)
        th._add_annotations(img.pk, scores, cls.labels, classifier)
        img.features.extracted = True
        img.features.classified = True
        img.features.save()

    def test_classify_for_unannotated_image(self):
        """Classify an image which has no annotations yet."""
        img = self.upload_image(self.user, self.source)
        self.classify(img)

        # Should have only robot annotations
        for ann in Annotation.objects.filter(image_id=img.id):
            self.assertTrue(is_robot_user(ann.user))

    def test_classify_for_unconfirmed_image(self):
        """Classify an image where all points have unconfirmed annotations.
        We'll assume we have a robot which is better than the previous (it's
        not _add_annotations()'s job to determine this)."""
        img = self.upload_image(self.user, self.source)

        classifier_1 = Classifier(source=self.source, valid=True)
        classifier_1.save()
        scores = [
            [0.8, 0.5, 0.5, 0.5],  # Point 1: A
            [0.5, 0.5, 0.5, 0.8],  # Point 2: D
            [0.5, 0.8, 0.5, 0.5],  # Point 3: B
        ]
        self.classify(img, classifier=classifier_1, scores=scores)

        classifier_2 = Classifier(source=self.source, valid=True)
        classifier_2.save()
        scores = [
            [0.6, 0.6, 0.7, 0.6],  # Point 1: C
            [0.6, 0.6, 0.6, 0.7],  # Point 2: D (same as before)
            [0.7, 0.6, 0.6, 0.6],  # Point 3: A
        ]
        self.classify(img, classifier=classifier_2, scores=scores)

        # Should have only robot annotations, with point 2 still being from
        # classifier 1
        for ann in Annotation.objects.filter(image_id=img.id):
            # Should be robot
            self.assertTrue(is_robot_user(ann.user))
            if ann.point.point_number == 2:
                self.assertTrue(ann.robot_version.pk == classifier_1.pk)
            else:
                self.assertTrue(ann.robot_version.pk == classifier_2.pk)

    def test_classify_for_partially_confirmed_image(self):
        """Classify an image where some, but not all points have confirmed
        annotations."""
        img = self.upload_image(self.user, self.source)
        # Human annotations
        self.add_annotations(self.user, img, {1: 'A'})
        # Robot annotations
        self.classify(img)

        for ann in Annotation.objects.filter(image_id=img.id):
            if ann.point.point_number == 1:
                # Should still be human
                self.assertFalse(is_robot_user(ann.user))
            else:
                # Should be robot
                self.assertTrue(is_robot_user(ann.user))

    def test_classify_for_fully_confirmed_image(self):
        """Classify an image where all points have confirmed annotations."""
        img = self.upload_image(self.user, self.source)
        # Human annotations
        self.add_annotations(
            self.user, img, {1: 'A', 2: 'B', 3: 'C'})
        # Robot annotations
        self.classify(img)

        # Should have only human annotations
        for ann in Annotation.objects.filter(image_id=img.id):
            self.assertFalse(is_robot_user(ann.user))

    def test_classify_scores_and_labels_match(self):
        img = self.upload_image(self.user, self.source)
        self.classify(img)

        # Check that the max score label matches the annotation label.
        for point in Point.objects.filter(image=img):
            ann = point.annotation
            scores = Score.objects.filter(point=point)
            posteriors = [score.score for score in scores]
            self.assertEqual(scores[np.argmax(posteriors)].label, ann.label)


@override_settings(FORCE_NO_BACKEND_SUBMIT=False)
class ExtractFeaturesTest(ClientTest):

    @classmethod
    def setUpTestData(cls):
        super(ExtractFeaturesTest, cls).setUpTestData()

        cls.user = cls.create_user()
        cls.source = cls.create_source(cls.user)

    def test_success(self):
        # After an image upload, features are ready to be submitted.
        img = self.upload_image(self.user, self.source)

        # Image upload already triggers feature submission to run after a
        # delay, but for testing purposes we'll run the task immediately.
        submit_features(img.id)

        # Then assuming we're using the mock backend, the result should be
        # available for collection immediately.
        collect_all_jobs()

        # Features should be successfully extracted.
        self.assertTrue(img.features.extracted)


@override_settings(FORCE_NO_BACKEND_SUBMIT=False, MIN_NBR_ANNOTATED_IMAGES=1)
class TrainClassifierTest(ClientTest):

    @classmethod
    def setUpTestData(cls):
        super(TrainClassifierTest, cls).setUpTestData()

        cls.user = cls.create_user()
        cls.source = cls.create_source(
            cls.user,
            point_generation_type=PointGen.Types.SIMPLE,
            simple_number_of_points=5)

        labels = cls.create_labels(cls.user, ['A', 'B'], "Group1")
        cls.create_labelset(cls.user, cls.source, labels)

        # Have an image with features
        cls.img = cls.upload_image(cls.user, cls.source)
        submit_features(cls.img.id)
        collect_all_jobs()

    def test_train_success(self):
        # Fully annotate the image
        self.add_annotations(
            self.user, self.img, {1: 'A', 2: 'B', 3: 'A', 4: 'A', 5: 'B'})
        # Now we have the minimum number of annotated images,
        # create a classifier
        submit_classifier(self.source.id)

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


@override_settings(FORCE_NO_BACKEND_SUBMIT=False, MIN_NBR_ANNOTATED_IMAGES=1)
class ClassifyImageTest(ClientTest):

    @classmethod
    def setUpTestData(cls):
        super(ClassifyImageTest, cls).setUpTestData()

        cls.user = cls.create_user()
        cls.source = cls.create_source(
            cls.user,
            point_generation_type=PointGen.Types.SIMPLE,
            simple_number_of_points=5)

        labels = cls.create_labels(cls.user, ['A', 'B'], "Group1")
        cls.create_labelset(cls.user, cls.source, labels)

        # Two images with features
        cls.img1 = cls.upload_image(cls.user, cls.source)
        submit_features(cls.img1.id)
        cls.img2 = cls.upload_image(cls.user, cls.source)
        submit_features(cls.img2.id)
        collect_all_jobs()
        # One image annotated, one not
        cls.add_annotations(
            cls.user, cls.img1, {1: 'A', 2: 'B', 3: 'A', 4: 'A', 5: 'B'})

        # Train classifier
        submit_classifier(cls.source.id)
        collect_all_jobs()

    def test_classify_unannotated_image(self):
        # TODO: This task call does not work using the MockBackend because
        # that backend doesn't actually create feature, model, and valresult
        # files yet. So this test fails.
        classify_image(self.img2.id)

        self.assertEqual(
            Annotation.objects.filter(image__id=self.img2.id).count(), 5)

