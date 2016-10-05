import time
import sys
from unittest import skipIf, skip

from django.conf import settings
from django.core.urlresolvers import reverse

from lib.test_utils import ClientTest, get_total_messages_in_jobs_queue

from annotations.models import Annotation
from images.models import Image, Source
from images.model_utils import PointGen

from .tasks import collect_all_jobs
from .models import Classifier, Features, Score





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
        self.img1 = self.upload_image_new(self.user, self.source)
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
        cls.user = cls.create_user() # we will always need a user. Let's crete it here.
        
    def wait_for_features_extracted(self, img_id):
        # Loop until jobs queue is empty or until features are extracted
        condition = lambda: Image.objects.get(id = img_id).features.extracted
        self._wait_helper(condition)

    def wait_for_classifier_trained(self, source, expected_nbr_classifiers):
        # Loop until jobs queue is empty or until another classifier has been trained
        condition = lambda: expected_nbr_classifiers == Classifier.objects.filter(source = source).count()
        self._wait_helper(condition)

    def _wait_helper(self, condition):
        time.sleep(2) # start by sleeping to allow jobs to be registered.
        while get_total_messages_in_jobs_queue() > 0 and not condition():
            print "z",; sys.stdout.flush()
            time.sleep(2)
            collect_all_jobs()
        time.sleep(1); collect_all_jobs(); time.sleep(1) #Sleep more to hedge against lags.

    def annotate(self, img_id, user, data):
        self.client.force_login(user)
        url = reverse('save_annotations_ajax', kwargs=dict(image_id = img_id))
        return self.client.post(url, data).json()    

@skip
@skipIf(not settings.DEFAULT_FILE_STORAGE == 'lib.storage_backends.MediaStorageS3', "Can't run backend tests locally")
@skipIf(get_total_messages_in_jobs_queue() > 10, "Too many messages in backend queue. Skipping this test.")
class ImageGetsFeaturesTest(BackendTest):
    """
    Check that features for a newly uploaded images automatically gets extracted. 
    """
    @classmethod
    def setUpTestData(cls):
        super(ImageGetsFeaturesTest, cls).setUpTestData()
        cls.source = cls.create_source(cls.user)
        
    def test_features_extraction(self):
        # Upload image
        img = self.upload_image_new(self.user, self.source)
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

        cls.source = cls.create_source(cls.user, point_generation_type=PointGen.Types.SIMPLE, simple_number_of_points=3)
        labels = cls.create_labels(cls.user, ['A', 'B'], 'GroupA')
        cls.create_labelset(cls.user, cls.source, labels)

        cls.dummy_annotations = dict(
            label_1='A', label_2='A', label_3='B',
            robot_1='false', robot_2='false', robot_3='false',
        )

    def test_automatic_training_upload(self):
        """
        Test that a classifier is trained after MIN_NBR_ANNOTATED_IMAGES are annotated and then have features (in that order)
        """
        # Upload and annotate just enough images for a classifier NOT to be trained.
        for itt in range(settings.MIN_NBR_ANNOTATED_IMAGES - 1): 
            img = self.upload_image_new(self.user, self.source)
            self.annotate(img.id, self.user, self.dummy_annotations)
            
        # Make sure features are extracted
        self.wait_for_features_extracted(img.id)

        # Give backend a chance to (erronously) train a classifier (there should not be any at this point)
        self.wait_for_classifier_trained(self.source, 1)

        # Make sure there are no classifiers in DB.
        self.assertEqual(Classifier.objects.filter(source = self.source).count(), 0)

        # Upload and annotate one more image.
        img = self.upload_image_new(self.user, self.source)
        self.annotate(img.id, self.user, self.dummy_annotations)

        # Make sure features are extracted
        self.wait_for_features_extracted(img.id)

        # Give backend a chance to process a backend robot training
        self.wait_for_classifier_trained(self.source, 1)

        # Now there shuold be a classifier.
        self.assertEqual(Classifier.objects.filter(source = self.source).count(), 1)


    def test_automatic_training_annotation(self):
        """
        Test that a classifier is trained after MIN_NBR_ANNOTATED_IMAGES have features and are annotated (in that order)
        """
       
        # Upload and MIN_NBR_ANNOTATED_IMAGES.
        for itt in range(settings.MIN_NBR_ANNOTATED_IMAGES): 
            img = self.upload_image_new(self.user, self.source)

        # Make sure features are extracted
        self.wait_for_features_extracted(img.id)

        # Make sure there are no classifiers in DB.
        self.assertEqual(Classifier.objects.filter(source = self.source).count(), 0)
        
        # Now, annotate them all.
        for img in Image.objects.filter(source = self.source):
            self.annotate(img.id, self.user, self.dummy_annotations)

        # Give backend a chance to process a backend robot training
        self.wait_for_classifier_trained(self.source, 1)

        # Now there shuold be a classifier.
        self.assertEqual(Classifier.objects.filter(source = self.source).count(), 1)



    



# TODO: Test:
# - Successful run of each backend task. OK
# - For applicable tasks, a subsequent task run after more data
#   becomes available. OK
# - Test multiple classifier training.
# - Classification does not overwrite confirmed annotations, including
#   in images which have some confirmed annotations and some not confirmed
# - Scores
#   + Test that scores disappear when points are removed.
#   + Test that scores are added when calling "classify".


@skip
@skipIf(not settings.DEFAULT_FILE_STORAGE == 'lib.storage_backends.MediaStorageS3', "Can't run backend tests locally")
@skipIf(get_total_messages_in_jobs_queue() > 10, "Too many messages in backend queue. Skipping this test.")
class DebugTest(ClientTest):
    
    @classmethod
    def setUpTestData(cls):
        super(DebugTest, cls).setUpTestData()
        settings.FORCE_NO_BACKEND_SUBMIT = False # Needed to enable backend.
        settings.MIN_NBR_ANNOTATED_IMAGES = 10 # Set to a lower amount for quicker test

        # Setup a source, user and labelset.
        cls.user = cls.create_user()

        cls.source = cls.create_source(
            cls.user, visibility=Source.VisibilityTypes.PUBLIC,
            point_generation_type=PointGen.Types.SIMPLE,
            simple_number_of_points=3,
        )
        labels = cls.create_labels(cls.user, ['A', 'B'], 'GroupA')
        cls.create_labelset(cls.user, cls.source, labels)

        cls.dummy_annotations = dict(
            label_1='A', label_2='A', label_3='B',
            robot_1='false', robot_2='false', robot_3='false',
        )

    def upload_and_annotate(self):
        self.client.force_login(self.user)
        img = self.upload_image_new(self.user, self.source)
        url = reverse('save_annotations_ajax', kwargs=dict(image_id = img.pk))
        response = self.client.post(url, self.dummy_annotations).json()
        print response
        return img

    def test_debug(self):
        img = self.upload_and_annotate()
        print 'nbr annotations:', Annotation.objects.filter(image = img).count()


