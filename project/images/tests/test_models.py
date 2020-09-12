from __future__ import unicode_literals
from io import BytesIO
import mock
from unittest import skip

from django.core.files.base import ContentFile
from django_migration_testcase import MigrationTest
from easy_thumbnails.files import get_thumbnailer
import piexif
from PIL import Image as PILImage

from annotations.model_utils import AnnotationAreaUtils
from images.models import Point
from images.model_utils import PointGen
from lib.tests.utils import ClientTest


class ImageExifOrientationTest(ClientTest):
    """
    Test images with EXIF orientation.
    """
    @classmethod
    def setUpTestData(cls):
        super(ImageExifOrientationTest, cls).setUpTestData()

        cls.user = cls.create_user()
        cls.source = cls.create_source(cls.user)
        labels = cls.create_labels(cls.user, ['label1'], 'group1')
        cls.labelset = cls.create_labelset(cls.user, cls.source, labels)

    def test_thumbnail_doesnt_use_exif_orientation(self):
        """
        Generated thumbnails should ignore the original image's EXIF
        orientation.
        """
        # Create an image with:
        # - A blue background
        # - 1 corner filled with red pixels
        blue_color = (0, 0, 255)
        red_color = (255, 0, 0)

        # EXIF specifying 90-degree right rotation
        zeroth_ifd = {piexif.ImageIFD.Orientation: 8}
        exif_dict = {'0th': zeroth_ifd}
        exif_bytes = piexif.dump(exif_dict)

        with PILImage.new('RGB', (100, 70), color=blue_color) as im:
            upper_left_20_by_20 = (0, 0, 20, 20)
            im.paste(red_color, upper_left_20_by_20)

            # Save image
            with BytesIO() as stream:
                im.save(stream, 'JPEG', exif=exif_bytes)
                image_file = ContentFile(stream.getvalue(), name='1.jpg')

        # Upload image
        img = self.upload_image(self.user, self.source, image_file=image_file)

        with PILImage.open(img.original_file) as im:
            exif_dict = piexif.load(im.info['exif'])
        self.assertEqual(
            exif_dict['0th'][piexif.ImageIFD.Orientation], 8,
            "Image should be saved with EXIF orientation")

        # Generate thumbnail of 50-pixel width
        opts = {'size': (50, 0)}
        thumbnail = get_thumbnailer(img.original_file).get_thumbnail(opts)

        # Check thumbnail file
        with PILImage.open(thumbnail.file) as thumb_im:
            self.assertEqual(
                thumb_im.size, (50, 35),
                "Thumbnail dimensions should have the same aspect ratio as"
                " the original image, un-rotated")
            self.assertNotIn(
                'exif', thumb_im.info,
                "Thumbnail should not have EXIF (we just want it to not have"
                " non-default EXIF orientation, but the actual result is that"
                " there is no EXIF, so we check for that)")

            # Check thumbnail file content. This is all JPEG, so we don't
            # expect exact color matches, but this code should manage to check
            # which corner is the red corner.
            upper_left_pixel = thumb_im.getpixel((0, 0))
            upper_left_r_greater_than_b = \
                upper_left_pixel[0] > upper_left_pixel[2]
            self.assertTrue(
                upper_left_r_greater_than_b,
                "Red corner should be the same corner as in the original"
                " image, indicating that the thumbnail content is un-rotated")


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


@skip("Fails on Travis after adding images 0024 migration.")
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
