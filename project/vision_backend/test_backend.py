import time
from unittest import skipIf

from django.conf import settings

from lib.test_utils import ClientTest, get_total_messages_in_jobs_queue
from images.models import Image
from .tasks import collect_all_jobs


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

@skipIf(not settings.DEFAULT_FILE_STORAGE == 'lib.storage_backends.MediaStorageS3', "Can't run backend tests locally")
@skipIf(get_total_messages_in_jobs_queue() > 10, "Too many messages in backend queue. Skipping this test.")
class ImageGetsFeaturesTest(ClientTest):
    """
    Check that features for a newly uploaded images automatically gets extracted. 
    """
    @classmethod
    def setUpTestData(cls):
        super(ImageGetsFeaturesTest, cls).setUpTestData()
        settings.FORCE_NO_BACKEND_SUBMIT = False
        cls.user = cls.create_user()
        cls.source = cls.create_source(cls.user)
        
    def test_features_extraction(self):

        self.img1 = self.upload_image_new(self.user, self.source)
        self.assertFalse(self.img1.features.extracted)

        # Loop until jobs queue is empty or until features are extracted
        while get_total_messages_in_jobs_queue() > 0 and not self.img1.features.extracted:
            print "z",
            time.sleep(2)
            collect_all_jobs()
            self.img1 = Image.objects.get(id = self.img1.id)

        self.assertTrue(self.img1.features.extracted)

# TODO: Test:
# - Successful run of each backend task
# - For applicable tasks, a subsequent task run after more data
#   becomes available.
# - Classification does not overwrite confirmed annotations, including
#   in images which have some confirmed annotations and some not confirmed
# - Scores
#   + Test that scores disappear when points are removed.
#   + Test that scores are added when calling "classify".
