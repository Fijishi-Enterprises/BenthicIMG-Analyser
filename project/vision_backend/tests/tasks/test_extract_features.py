from django.conf import settings
from django.core.files.storage import get_storage_class
from django.test.utils import patch_logger
from spacer.data_classes import ImageFeatures

from vision_backend.tasks import collect_all_jobs, submit_features
from .utils import BaseTaskTest


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
            self.rowcols_with_dupes_included, sorted(rowcols),
            "Feature rowcols should match the actual points including dupes")


class AbortCasesTest(BaseTaskTest):
    """
    Test cases where the task or collection would abort before reaching the
    end.
    """

    def test_nonexistent_image(self):
        """Try to extract features for a nonexistent image ID."""
        # To get a nonexistent image ID, upload an image, get its ID, then
        # delete the image.
        img = self.upload_image(self.user, self.source)
        image_id = img.pk
        img.delete()

        # patch_logger is an undocumented Django test utility. It lets us check
        # logged messages.
        # https://stackoverflow.com/a/54055056
        with patch_logger('vision_backend.tasks', 'info') as log_messages:
            submit_features(image_id)

            log_message = "Image {} does not exist.".format(image_id)
            self.assertIn(
                log_message, log_messages,
                "Should log the appropriate message")

    def test_already_has_features(self):
        """Try to extract features for an image which already has features."""
        img = self.upload_image(self.user, self.source)
        # Collect feature extraction result
        collect_all_jobs()

        with patch_logger('vision_backend.tasks', 'info') as log_messages:
            submit_features(img.pk)

            log_message = (
                "Image {} [Source: {} [{}]] already has features".format(
                    img.pk, img.source, img.source_id))
            self.assertIn(
                log_message, log_messages,
                "Should log the appropriate message")
