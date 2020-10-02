from __future__ import unicode_literals
from io import BytesIO

from django.core.files.base import ContentFile
from django_migration_testcase import MigrationTest
from easy_thumbnails.files import get_thumbnailer
import piexif
from PIL import Image as PILImage

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


class PopulateLastAnnotationMigrationTest(MigrationTest, ClientTest):

    app_name = 'images'
    before = '0024'
    after = '0025'

    def test_migration(self):
        user = self.create_user()
        source = self.create_source(
            user,
            point_generation_type=PointGen.Types.SIMPLE,
            simple_number_of_points=2)
        labels = self.create_labels(user, ['A', 'B'], 'GroupA')
        self.create_labelset(user, source, labels)

        # No annotations.
        img1 = self.upload_image(user, source)

        # One annotation.
        img2 = self.upload_image(user, source)
        self.add_annotations(user, img2, {1: 'A'})

        # Two annotations, latest on point 1.
        img3 = self.upload_image(user, source)
        self.add_annotations(user, img3, {2: 'B'})
        self.add_annotations(user, img3, {1: 'A'})

        # Two annotations, latest on point 2.
        img4 = self.upload_image(user, source)
        self.add_annotations(user, img4, {1: 'A'})
        self.add_annotations(user, img4, {2: 'B'})

        # Reset last_annotation fields.
        img1.last_annotation = None
        img1.save()
        img2.last_annotation = None
        img2.save()
        img3.last_annotation = None
        img3.save()
        img4.last_annotation = None
        img4.save()

        # Set last_annotation fields with the migration.
        self.run_migration()

        # Check last_annotation values.
        img1.refresh_from_db()
        self.assertIsNone(img1.last_annotation)

        img2.refresh_from_db()
        self.assertIsNotNone(img2.last_annotation)
        self.assertEqual(
            img2.last_annotation.pk,
            img2.annotation_set.get(point__point_number=1).pk)

        img3.refresh_from_db()
        self.assertIsNotNone(img3.last_annotation)
        self.assertEqual(
            img3.last_annotation.pk,
            img3.annotation_set.get(point__point_number=1).pk)

        img4.refresh_from_db()
        self.assertIsNotNone(img4.last_annotation)
        self.assertEqual(
            img4.last_annotation.pk,
            img4.annotation_set.get(point__point_number=2).pk)
