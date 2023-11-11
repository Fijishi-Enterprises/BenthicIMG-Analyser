from django.conf import settings
from django.core.files.storage import get_storage_class
from django.test import override_settings

from images.model_utils import PointGen
from jobs.tests.utils import do_job, queue_and_run_job
from lib.tests.utils import ClientTest
from upload.tests.utils import UploadAnnotationsCsvTestMixin


def queue_and_run_collect_spacer_jobs():
    queue_and_run_job('collect_spacer_jobs')


@override_settings(
    SPACER_QUEUE_CHOICE='vision_backend.queues.LocalQueue',
    # Sometimes it helps to run certain periodic jobs (particularly
    # collect_spacer_jobs) only when we explicitly want to.
    ENABLE_PERIODIC_JOBS=False,
)
class BaseTaskTest(ClientTest, UploadAnnotationsCsvTestMixin):
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

    @classmethod
    def upload_image_with_annotations(cls, filename):
        img = cls.upload_image(
            cls.user, cls.source, image_options=dict(filename=filename))
        cls.add_annotations(
            cls.user, img, {1: 'A', 2: 'B', 3: 'A', 4: 'A', 5: 'B'})
        return img

    @classmethod
    def upload_images_for_training(
        cls, train_image_count=None, val_image_count=1,
    ):
        if not train_image_count:
            # Provide enough data for initial training
            train_image_count = settings.MIN_NBR_ANNOTATED_IMAGES

        train_images = []
        val_images = []

        for _ in range(train_image_count):
            train_images.append(
                cls.upload_image_with_annotations(
                    'train{}.png'.format(cls.image_count)))
        for _ in range(val_image_count):
            val_images.append(
                cls.upload_image_with_annotations(
                    'val{}.png'.format(cls.image_count)))

        return train_images, val_images

    @classmethod
    def upload_data_and_train_classifier(cls, new_train_images_count=None):
        train_images, val_images = cls.upload_images_for_training(
            train_image_count=new_train_images_count, val_image_count=1)
        # Extract features
        # In most cases, run_scheduled_jobs_until_empty() would be equivalent
        # to these do_job() calls, but sometimes it's useful to make sure no
        # other job runs in the meantime.
        for image in [*train_images, *val_images]:
            do_job('extract_features', image.pk, source_id=cls.source.pk)
        queue_and_run_collect_spacer_jobs()
        # Train classifier
        do_job('train_classifier', cls.source.pk, source_id=cls.source.pk)
        queue_and_run_collect_spacer_jobs()

    @classmethod
    def upload_image_for_classification(cls):
        # Image without annotations
        image = cls.upload_image(cls.user, cls.source)
        # Extract features
        do_job('extract_features', image.pk, source_id=cls.source.pk)
        queue_and_run_collect_spacer_jobs()

        return image

    @classmethod
    def upload_image_and_machine_classify(cls):
        # Image without annotations, with features extracted
        image = cls.upload_image_for_classification()
        # Classify image (assumes there's already a classifier)
        do_job('classify_features', image.pk, source_id=cls.source.pk)

        return image

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
        csv_file = self.make_annotations_file('A.csv', rows)
        self.preview_annotations(
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
