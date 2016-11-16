import time
import sys
from unittest import skipIf, skip
import numpy as np

from django.conf import settings
from django.core.urlresolvers import reverse

from lib.test_utils import ClientTest, get_total_messages_in_jobs_queue
from accounts.utils import get_robot_user

from annotations.models import Annotation
from labels.models import Label
from images.models import Source, Image, Point
from images.model_utils import PointGen

from .tasks import collect_all_jobs
from .models import Classifier, Features, Score

"""
This file tests the mechanics of the vision_backend app. These are slow to run since they must allow actual processing to take place on the backend.
"""


class ImageInitialStatusTest(ClientTest):
    """
    Check a newly uploaded image's status (as relevant to the vision backend).
    """
    @classmethod
    def setUpTestData(cls):
        super(ImageInitialStatusTest, cls).setUpTestData()

    def test_features_extracted_false(self):
        self.user = self.create_user()
        self.source = self.create_source(self.user)
        self.img1 = self.upload_image(self.user, self.source)
        self.assertFalse(self.img1.features.extracted)


class BackendTest(ClientTest):
    """
    Superclass for tests that need to use the distributed backend.
    """

    @classmethod
    def setUpTestData(cls):
        super(BackendTest, cls).setUpTestData()
        settings.FORCE_NO_BACKEND_SUBMIT = False # Needed to enable backend.
        settings.MIN_NBR_ANNOTATED_IMAGES = 10 # Set to a lower amount for quicker test
        cls.user = cls.create_user() # we will always need a user. 

        cls.dummy_annotations = dict(
            label_1='A', label_2='A', label_3='B',
            robot_1='false', robot_2='false', robot_3='false',
        )

        cls.source = cls.create_source(cls.user, point_generation_type=PointGen.Types.SIMPLE, simple_number_of_points=3)
        
        labels = cls.create_labels(cls.user, ['A', 'B', 'C', 'D', 'E', 'F'], "Group1")

        cls.create_labelset(cls.user, cls.source, labels.filter(
            name__in=['A', 'B', 'C', 'D', 'E', 'F'])
        )
    
    @classmethod    
    def wait_for_features_extracted(self, img_id):
        # Loop until jobs queue is empty or until features are extracted
        condition = lambda: Image.objects.get(id = img_id).features.extracted
        self._wait_helper(condition)

    @classmethod    
    def wait_for_classifier_trained(self, source, expected_nbr_classifiers):
        # Loop until jobs queue is empty or until another classifier has been trained
        condition = lambda: expected_nbr_classifiers == Classifier.objects.filter(source = source, valid = True).count()
        self._wait_helper(condition)

    @classmethod
    def _wait_helper(self, condition):
        if condition():
            return
        itt = 0
        converged = False
        while not converged:
            itt += 1
            sys.stdout.write('z')
            sys.stdout.flush()
            time.sleep(2)
            collect_all_jobs()
            converged = condition() or (get_total_messages_in_jobs_queue() == 0 and itt > 2)
        collect_all_jobs()            
        time.sleep(2)

    @classmethod
    def annotate(self, img_id, user, data):
        self.client.force_login(user)
        url = reverse('save_annotations_ajax', kwargs=dict(image_id = img_id))
        return self.client.post(url, data).json()


class BackendTestWithClassifier(BackendTest):
    @classmethod
    def setUpTestData(cls):
        super(BackendTestWithClassifier, cls).setUpTestData()

        # Train a classifier.
        for itt in range(settings.MIN_NBR_ANNOTATED_IMAGES): 
            img = cls.upload_image(cls.user, cls.source)
            cls.annotate(img.id, cls.user, cls.dummy_annotations)

        # Make sure features are extracted
        for img in Image.objects.filter(source = cls.source):
            cls.wait_for_features_extracted(img.id)
        
        # Make sure classifier is trained.                
        cls.wait_for_classifier_trained(cls.source, 1)

@skipIf(not settings.DEFAULT_FILE_STORAGE == 'lib.storage_backends.MediaStorageS3', "Can't run backend tests locally")
@skipIf(get_total_messages_in_jobs_queue() > 10, "Too many messages in backend queue. Skipping this test.")
class ImageGetsFeaturesTest(BackendTest):
    """
    Check that features for a newly uploaded images automatically gets extracted. 
    """
    @classmethod
    def setUpTestData(cls):
        super(ImageGetsFeaturesTest, cls).setUpTestData()
        
    def test_features_extraction(self):
        # Upload image
        img = self.upload_image(self.user, self.source)
        # No features initially.
        self.assertFalse(Image.objects.get(id = img.id).features.extracted)
        # Wait for backend.
        self.wait_for_features_extracted(img.id)
        # Now there should be features.
        self.assertTrue(Image.objects.get(id = img.id).features.extracted)

@skipIf(not settings.DEFAULT_FILE_STORAGE == 'lib.storage_backends.MediaStorageS3', "Can't run backend tests locally")
@skipIf(get_total_messages_in_jobs_queue() > 10, "Too many messages in backend queue. Skipping this test.")
class TrainClassifierTest(BackendTest):
    """
    Check that robot get's trained automatically.
    This test uses dummy data and annotations.
    """

    @classmethod
    def setUpTestData(cls):
        super(TrainClassifierTest, cls).setUpTestData()

    def test_automatic_training_upload(self):
        """
        Test that a classifier is trained after MIN_NBR_ANNOTATED_IMAGES are annotated and then have features (in that order)
        """
        # Upload and annotate just enough images for a classifier NOT to be trained.
        for itt in range(settings.MIN_NBR_ANNOTATED_IMAGES - 1): 
            img = self.upload_image(self.user, self.source)
            self.annotate(img.id, self.user, self.dummy_annotations)
            
        # Make sure features are extracted
        for img in Image.objects.filter(source = self.source):
            self.wait_for_features_extracted(img.id)

        # Give backend a chance to (erronously) train a classifier (there should not be any at this point)
        self.wait_for_classifier_trained(self.source, 1)

        # Make sure there are no classifiers in DB.
        self.assertEqual(Classifier.objects.filter(source = self.source).count(), 0)

        # Upload and annotate one more image.
        img = self.upload_image(self.user, self.source)
        self.annotate(img.id, self.user, self.dummy_annotations)

        # Make sure features are extracted
        self.wait_for_features_extracted(img.id)

        # There should be one non-valid now (means that it is out for training).
        self.assertEqual(Classifier.objects.filter(source = self.source, valid=True).count(), 0)
        self.assertEqual(Classifier.objects.filter(source = self.source, valid=False).count(), 1)

        # Give backend a chance to train a classifier.
        self.wait_for_classifier_trained(self.source, 1)

        # Now there shuold be a valid classifier.
        self.assertEqual(Classifier.objects.filter(source = self.source, valid=True).count(), 1)
        self.assertEqual(Classifier.objects.filter(source = self.source, valid=False).count(), 0)


    def test_automatic_training_annotation(self):
        """
        Test that a classifier is trained after MIN_NBR_ANNOTATED_IMAGES have features and are annotated (in that order)
        """
       
        # Upload and MIN_NBR_ANNOTATED_IMAGES.
        for itt in range(settings.MIN_NBR_ANNOTATED_IMAGES): 
            img = self.upload_image(self.user, self.source)

        # Make sure features are extracted
        for img in Image.objects.filter(source = self.source):
            self.wait_for_features_extracted(img.id)
        
        # Make sure there are no classifiers in DB.
        self.assertEqual(Classifier.objects.filter(source = self.source).count(), 0)
        
        # Now, annotate them all.
        for img in Image.objects.filter(source = self.source):
            self.annotate(img.id, self.user, self.dummy_annotations)

        # There should be one non-valid now (means that it is out for training).
        self.assertEqual(Classifier.objects.filter(source = self.source, valid=True).count(), 0)
        self.assertEqual(Classifier.objects.filter(source = self.source, valid=False).count(), 1)

        # Give backend a chance to train a classifier.
        self.wait_for_classifier_trained(self.source, 1)

        # Now there shuold be a valid classifier.
        self.assertEqual(Classifier.objects.filter(source = self.source, valid=True).count(), 1)
        self.assertEqual(Classifier.objects.filter(source = self.source, valid=False).count(), 0)
    
@skip #this test is unreliable.
@skipIf(not settings.DEFAULT_FILE_STORAGE == 'lib.storage_backends.MediaStorageS3', "Can't run backend tests locally")
@skipIf(get_total_messages_in_jobs_queue() > 10, "Too many messages in backend queue. Skipping this test.")
class ResetLabelSetTest(BackendTestWithClassifier):

    @classmethod
    def setUpTestData(cls):
        super(ResetLabelSetTest, cls).setUpTestData()

    def test_labelset_change_cleanup(self):
        """
        Test that if the labelset changes all scores, classifiers, and annotations are wiped.
        """

        # Upload an image
        img1 = self.upload_image(self.user, self.source)
        
        # Wait for backend.
        self.wait_for_features_extracted(img1.id)
               
        # Check that img1 has 15 scores (3 points * min(5, nbr_labels))
        self.assertEqual(Score.objects.filter(image_id = img1.id).count(), 3 * 5)

        # Change the labelset.
        self.client.force_login(self.user)
        label_pks = [Label.objects.get(name=name).pk for name in ['A', 'B']]
        response = self.client.post(
            reverse('labelset_add', args=[self.source.pk]),
            dict(label_ids=','.join(str(pk) for pk in label_pks)),
            follow=True,
        )

        # Check that there is no valid classifier, but one in process
        self.assertEqual(Classifier.objects.filter(source = self.source, valid=True).count(), 0)
        self.assertEqual(Classifier.objects.filter(source = self.source, valid=False).count(), 1)

        # Check that img1 has no annotations
        self.assertEqual(Annotation.objects.filter(image_id = img1.id).count(), 0)
        
        # Check that img1 has no scores.
        self.assertEqual(Score.objects.filter(image_id = img1.id).count(), 0)
    
        # Wait a while, and there should be a new classifier
        self.wait_for_classifier_trained(self.source, 1)
        self.assertEqual(Classifier.objects.filter(source = self.source, valid=True).count(), 1)
        self.assertEqual(Classifier.objects.filter(source = self.source, valid=False).count(), 0)
        
        # And img1 should has 6 score (3 points * min(5, nbr_labels))
        self.assertEqual(Score.objects.filter(image_id = img1.id).count(), 3 * 2)

@skip #this test is unreliable.
@skipIf(not settings.DEFAULT_FILE_STORAGE == 'lib.storage_backends.MediaStorageS3', "Can't run backend tests locally")
@skipIf(get_total_messages_in_jobs_queue() > 10, "Too many messages in backend queue. Skipping this test.")
class ImageClassification(BackendTestWithClassifier):
    """
    Tests various aspects of classifying images. 
    NOTE: some of these tests tend to fail irradically due to race conditions.
    My assessment is that it is specific to the tests, not the actual server.
    """

    @classmethod
    def setUpTestData(cls):
        super(ImageClassification, cls).setUpTestData()


        cls.partial_dummy_annotations = dict(
            label_1='A',
            robot_1='false',
        )

    def test_classify_image(self):
        """
        Test basic dynamics of image upload.
        """
        # Upload three images
        img1 = self.upload_image(self.user, self.source)
        img2 = self.upload_image(self.user, self.source)
        img3 = self.upload_image(self.user, self.source)
        
        # Annotate the second one partially and the third fully
        self.annotate(img2.id, self.user, self.partial_dummy_annotations)
        self.annotate(img3.id, self.user, self.dummy_annotations)

        # Remember which were annotated for img2
        human_anns = list(Annotation.objects.filter(image_id = img2.id))

        # Wait for backend.
        for img in [img1, img2, img3]:
            self.wait_for_features_extracted(img.id)

        # Check features flags. All should have features and be classified since there is a classifier. Even confirmed images should be classified.
        for img in [img1, img2, img3]:
            self.assertTrue(Image.objects.get(id = img.id).features.extracted)
            self.assertTrue(Image.objects.get(id = img.id).features.classified)

        # Check the annotations. 

        # Img1 whould have only robot annotations
        for ann in Annotation.objects.filter(image_id = img1.id):
            self.assertTrue(ann.user == get_robot_user())

        # Img2 should have a mix.
        for ann in Annotation.objects.filter(image_id = img2.id):
            if ann in human_anns:
                self.assertFalse(ann.user == get_robot_user())
            else:
                self.assertTrue(ann.user == get_robot_user())

        # Img3 should have only manual annotations.    
        for ann in Annotation.objects.filter(image_id = img3.id):
            self.assertFalse(ann.user == get_robot_user())

        # Check the scores.
        for img in [img1, img2, img3]:
            scores = Score.objects.filter(image_id = img.id)
            self.assertEqual(len(scores), 5 * 3) # 5 labels and 5 points.
            for score in scores:
                self.assertTrue(score.score >= 0)
                self.assertTrue(score.score <= 100)

        # Check that max score label corresponds to the annotation for each point for img1.
        for point in Point.objects.filter(image = img1):
            ann = Annotation.objects.get(point = point)
            scores = Score.objects.filter(point = point)
            posteriors = [score.score for score in scores]
            self.assertEqual(scores[np.argmax(posteriors)].label, ann.label)

    def test_point_score_cascade_delete(self):
        """
        If a point is deleted all scores for that point should be deleted.
        """
        img1 = self.upload_image(self.user, self.source)
        self.wait_for_features_extracted(img1.id)

        self.assertEqual(Score.objects.filter(image = img1).count(), 3 * 5)
        # remove one point
        points = Point.objects.filter(image = img1)
        points[0].delete()

        # Now all scores for that point should be gone.
        self.assertEqual(Score.objects.filter(image = img1).count(), 2 * 5)

    def test_point_generated_features_reset(self):
        """
        If we genereate new point, features must be reset.
        """
        img1 = self.upload_image(self.user, self.source)
        self.wait_for_features_extracted(img1.id)

        self.assertTrue(Image.objects.get(id = img1.id).features.extracted)
        self.assertTrue(Image.objects.get(id = img1.id).features.classified)

        self.client.force_login(self.user)
        url = reverse('image_detail', kwargs=dict(image_id = img1.id))
        data = dict(
            regenerate_point_locations="Any arbitrary string goes here"
        )
        self.client.post(url, data)

        # Now features should be reset
        self.assertFalse(Image.objects.get(id = img1.id).features.extracted)
        self.assertFalse(Image.objects.get(id = img1.id).features.classified)

        self.wait_for_features_extracted(img1.id)

        # And re-generated!
        self.assertTrue(Image.objects.get(id = img1.id).features.extracted)
        self.assertTrue(Image.objects.get(id = img1.id).features.classified)


