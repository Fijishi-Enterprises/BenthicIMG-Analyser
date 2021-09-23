from django.core.files.storage import get_storage_class
from django.test import override_settings
import spacer.config as spacer_config

from images.model_utils import PointGen
from lib.tests.utils import ClientTest
from upload.tests.utils import UploadAnnotationsTestMixin
from vision_backend.tasks import collect_all_jobs, submit_classifier


# Note that spacer also has its own minimum image count for training.
@override_settings(MIN_NBR_ANNOTATED_IMAGES=1)
@override_settings(SPACER_QUEUE_CHOICE='vision_backend.queues.LocalQueue')
class BaseTaskTest(ClientTest, UploadAnnotationsTestMixin):
    """Base test class for testing the backend's 'main' tasks."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()

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

    def upload_data_and_train_classifier(self):
        # Provide enough data for training
        self.upload_images_for_training(
            train_image_count=spacer_config.MIN_TRAINIMAGES, val_image_count=1)
        # Process feature extraction results
        collect_all_jobs()

        # Train classifier
        submit_classifier(self.source.pk)
        collect_all_jobs()

    def upload_image_and_machine_classify(self, user, source):
        # Image without annotations
        img = self.upload_image(user, source)
        # Process feature extraction results + classify image
        collect_all_jobs()

        return img

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
