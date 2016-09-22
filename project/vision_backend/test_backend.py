from lib.test_utils import ClientTest


class ImageInitialStatusTest(ClientTest):
    """
    Check a newly uploaded image's status (as relevant to the vision backend).
    """
    @classmethod
    def setUpTestData(cls):
        super(ImageInitialStatusTest, cls).setUpTestData()

        cls.user = cls.create_user()
        cls.source = cls.create_source(cls.user)
        cls.img1 = cls.upload_image_new(cls.user, cls.source)

    def test_features_extracted_false(self):
        self.assertFalse(self.img1.features.extracted)


# TODO: Test:
# - Successful run of each backend task
# - For applicable tasks, a subsequent task run after more data
#   becomes available
# - Classification does not overwrite confirmed annotations, including
#   in images which have some confirmed annotations and some not confirmed
