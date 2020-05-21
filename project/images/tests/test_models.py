from __future__ import unicode_literals
import mock

from django_migration_testcase import MigrationTest

from annotations.model_utils import AnnotationAreaUtils
from images.models import Point
from images.model_utils import PointGen
from lib.tests.utils import ClientTest


class PointValidationTest(ClientTest):

    def test_bounds_checks(self):
        user = self.create_user()
        source = self.create_source(user)
        image = self.upload_image(
            user, source, image_options=dict(width=50, height=40))

        # OK
        point = Point(image=image, column=0, row=0, point_number=1)
        point.save()
        point = Point(image=image, column=49, row=39, point_number=2)
        point.save()

        # Errors
        point = Point(image=image, column=0, row=-1, point_number=3)
        with self.assertRaisesMessage(AssertionError, "Row below minimum"):
            point.save()

        point = Point(image=image, column=49, row=40, point_number=3)
        with self.assertRaisesMessage(AssertionError, "Row above maximum"):
            point.save()

        point = Point(image=image, column=-1, row=0, point_number=3)
        with self.assertRaisesMessage(AssertionError, "Column below minimum"):
            point.save()

        point = Point(image=image, column=50, row=39, point_number=3)
        with self.assertRaisesMessage(AssertionError, "Column above maximum"):
            point.save()


def save_without_checks(self, *args, **kwargs):
    """
    Mock version of Point.save().
    Doesn't run assertions, so we can save any row/column values we want.
    """
    super(Point, self).save(*args, **kwargs)


class PointRowcolIndexingMigrationTest(MigrationTest, ClientTest):

    app_name = 'images'
    before = '0022'
    after = '0023'

    def test_migration(self):
        user = self.create_user()
        source = self.create_source(
            user,
            min_x=0,
            max_x=100,
            min_y=0,
            max_y=100,
            point_generation_type=PointGen.Types.SIMPLE,
            simple_number_of_points=1)

        img1 = self.upload_image(
            user, source, image_options=dict(width=50, height=50))
        img2 = self.upload_image(
            user, source, image_options=dict(width=50, height=50))

        # Create points manually and without checks so we can set the
        # rows/columns we want.
        Point.objects.all().delete()
        with mock.patch.object(Point, 'save', save_without_checks):
            point = Point(image=img1, point_number=1, row=1, column=50)
            point.save()
            point = Point(image=img2, point_number=1, row=29, column=1)
            point.save()

        # Create a pixel-based annotation area for only one image. Leave the
        # other as a percent-based area.
        img2.metadata.annotation_area = \
            AnnotationAreaUtils.pixels_to_db_format(1, 15, 1, 45)
        img2.metadata.save()

        # Convert from 1-indexing to 0-indexing.
        self.run_migration()

        # Check that Points have been converted.
        point = Point.objects.get(image=img1)
        self.assertEqual(point.row, 0)
        self.assertEqual(point.column, 49)
        point = Point.objects.get(image=img2)
        self.assertEqual(point.row, 28)
        self.assertEqual(point.column, 0)

        # Check that pixel-based annotation areas have been converted,
        # and that percent-based ones stay the same.
        img1.metadata.refresh_from_db()
        self.assertEqual(img1.metadata.annotation_area, '0;100;0;100')
        img2.metadata.refresh_from_db()
        self.assertEqual(img2.metadata.annotation_area, '0,14,0,44')
