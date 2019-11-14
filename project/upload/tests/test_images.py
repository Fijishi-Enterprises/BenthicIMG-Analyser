from __future__ import unicode_literals
from io import BytesIO
import json
import re

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import DefaultStorage
from django.urls import reverse
from django.utils import timezone

from images.models import Image
from lib.tests.utils import (
    ClientTest, sample_image_as_file, create_sample_image)


class UploadImagePreviewTest(ClientTest):
    """
    Test the upload-image preview view.
    """
    @classmethod
    def setUpTestData(cls):
        super(UploadImagePreviewTest, cls).setUpTestData()

        cls.user = cls.create_user()
        cls.source = cls.create_source(cls.user)

        cls.img1 = cls.upload_image(
            cls.user, cls.source, image_options=dict(filename='1.png'))
        cls.img2 = cls.upload_image(
            cls.user, cls.source, image_options=dict(filename='2.png'))

    def test_no_dupe(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse('upload_images_preview_ajax', args=[self.source.pk]),
            dict(file_info=json.dumps([dict(filename='3.png', size=1024)])),
        )

        response_json = response.json()
        self.assertDictEqual(
            response_json,
            dict(statuses=[dict(ok=True)]),
        )

    def test_detect_dupe(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse('upload_images_preview_ajax', args=[self.source.pk]),
            dict(file_info=json.dumps([dict(filename='1.png', size=1024)])),
        )

        response_json = response.json()
        self.assertDictEqual(
            response_json,
            dict(
                statuses=[dict(
                    error="Image with this name already exists",
                    url=reverse('image_detail', args=[self.img1.id]),
                )]
            ),
        )

    def test_detect_multiple_dupes(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse('upload_images_preview_ajax', args=[self.source.pk]),
            dict(file_info=json.dumps([
                dict(filename='1.png', size=1024),
                dict(filename='2.png', size=1024),
                dict(filename='3.png', size=1024),
            ])),
        )

        response_json = response.json()
        self.assertDictEqual(
            response_json,
            dict(
                statuses=[
                    dict(
                        error="Image with this name already exists",
                        url=reverse('image_detail', args=[self.img1.id]),
                    ),
                    dict(
                        error="Image with this name already exists",
                        url=reverse('image_detail', args=[self.img2.id]),
                    ),
                    dict(
                        ok=True,
                    ),
                ]
            ),
        )


class UploadImageTest(ClientTest):
    """
    Upload a valid image.
    """
    @classmethod
    def setUpTestData(cls):
        super(UploadImageTest, cls).setUpTestData()

        cls.user = cls.create_user()
        cls.source = cls.create_source(cls.user)

    def test_valid_png(self):
        """ .png created using the PIL. """
        self.client.force_login(self.user)
        response = self.client.post(
            reverse('upload_images_ajax', args=[self.source.pk]),
            dict(file=sample_image_as_file('1.png'), name='1.png')
        )

        response_json = response.json()
        self.assertEqual(response_json['success'], True)
        image_id = response_json['image_id']
        image = Image.objects.get(pk=image_id)
        self.assertEqual(image.metadata.name, '1.png')

    def test_valid_jpg(self):
        """ .jpg created using the PIL. """
        self.client.force_login(self.user)
        response = self.client.post(
            reverse('upload_images_ajax', args=[self.source.pk]),
            dict(file=sample_image_as_file('A.jpg'), name='A.jpg')
        )

        response_json = response.json()
        self.assertEqual(response_json['success'], True)
        image_id = response_json['image_id']
        image = Image.objects.get(pk=image_id)
        self.assertEqual(image.metadata.name, 'A.jpg')

    def test_image_fields(self):
        """
        Upload an image and see if the fields have been set correctly.
        """
        datetime_before_upload = timezone.now()

        image_file = sample_image_as_file(
            '1.png',
            image_options=dict(
                width=600, height=450,
            ),
        )

        self.client.force_login(self.user)
        post_dict = dict(file=image_file, name=image_file.name)
        response = self.client.post(
            reverse('upload_images_ajax', args=[self.source.pk]),
            post_dict,
        )

        response_json = response.json()
        image_id = response_json['image_id']
        img = Image.objects.get(pk=image_id)

        # Check that the filepath follows the expected pattern
        image_filepath_regex = re.compile(
            settings.IMAGE_FILE_PATTERN
            .replace('{name}', r'[a-z0-9]+')
            .replace('{extension}', r'\.png')
        )
        self.assertRegexpMatches(
            str(img.original_file), image_filepath_regex)

        self.assertEqual(img.original_width, 600)
        self.assertEqual(img.original_height, 450)

        self.assertTrue(datetime_before_upload <= img.upload_date)
        self.assertTrue(img.upload_date <= timezone.now())

        # Check that the user who uploaded the image is the
        # currently logged in user.
        self.assertEqual(img.uploaded_by.pk, self.user.pk)

    def test_file_existence(self):
        """Uploaded file should exist in storage."""
        self.client.force_login(self.user)
        response = self.client.post(
            reverse('upload_images_ajax', args=[self.source.pk]),
            dict(file=sample_image_as_file('1.png'), name='1.png')
        )

        response_json = response.json()
        self.assertEqual(response_json['success'], True)
        image_id = response_json['image_id']
        img = Image.objects.get(pk=image_id)

        storage = DefaultStorage()
        self.assertTrue(storage.exists(img.original_file.name))


class UploadImageFormatTest(ClientTest):
    """
    Tests pertaining to filetype, filesize and dimensions.
    """
    @classmethod
    def setUpTestData(cls):
        super(UploadImageFormatTest, cls).setUpTestData()

        cls.user = cls.create_user()
        cls.source = cls.create_source(cls.user)

    def test_non_image(self):
        """Text file. Should get an error."""
        self.client.force_login(self.user)
        response = self.client.post(
            reverse('upload_images_ajax', args=[self.source.pk]),
            dict(file=ContentFile('some text', name='1.txt'), name='1.txt'),
        )

        response_json = response.json()
        self.assertDictEqual(
            response_json,
            dict(error=(
                "Image file: The file is either a corrupt image,"
                " or in a file format that we don't support."
            ))
        )

    def test_unsupported_image_type(self):
        """An image, but not a supported type. Should get an error."""
        self.client.force_login(self.user)

        im = create_sample_image()
        with BytesIO() as stream:
            im.save(stream, 'BMP')
            bmp_file = ContentFile(stream.getvalue(), name='1.bmp')

        response = self.client.post(
            reverse('upload_images_ajax', args=[self.source.pk]),
            dict(file=bmp_file, name=bmp_file.name),
        )

        response_json = response.json()
        self.assertDictEqual(
            response_json,
            dict(error="Image file: This image file format isn't supported.")
        )

    def test_empty_file(self):
        """0-byte file. Should get an error."""
        self.client.force_login(self.user)
        response = self.client.post(
            reverse('upload_images_ajax', args=[self.source.pk]),
            dict(file=ContentFile(bytes(), name='1.png'), name='1.png'),
        )

        response_json = response.json()
        self.assertDictEqual(
            response_json,
            dict(error="Image file: The submitted file is empty.")
        )

    def test_max_image_dimensions_1(self):
        """Should check the max image width."""
        image_file = sample_image_as_file(
            '1.png', image_options=dict(width=600, height=450),
        )

        self.client.force_login(self.user)
        post_dict = dict(file=image_file, name=image_file.name)
        with self.settings(IMAGE_UPLOAD_MAX_DIMENSIONS=(599, 1000)):
            response = self.client.post(
                reverse('upload_images_ajax', args=[self.source.pk]),
                post_dict,
            )

        response_json = response.json()
        self.assertDictEqual(
            response_json,
            dict(error=(
                "Image file: Ensure the image dimensions"
                " are at most 599 x 1000."))
        )

    def test_max_image_dimensions_2(self):
        """Should check the max image height."""
        image_file = sample_image_as_file(
            '1.png', image_options=dict(width=600, height=450),
        )

        self.client.force_login(self.user)
        post_dict = dict(file=image_file, name=image_file.name)
        with self.settings(IMAGE_UPLOAD_MAX_DIMENSIONS=(1000, 449)):
            response = self.client.post(
                reverse('upload_images_ajax', args=[self.source.pk]),
                post_dict,
            )

        response_json = response.json()
        self.assertDictEqual(
            response_json,
            dict(error=(
                "Image file: Ensure the image dimensions"
                " are at most 1000 x 449."))
        )

    def test_max_filesize(self):
        """Should check the max filesize in the upload preview."""
        self.client.force_login(self.user)

        post_dict = dict(file_info=json.dumps(
            [dict(filename='1.png', size=1024*1024*1024)]
        ))

        with self.settings(IMAGE_UPLOAD_MAX_FILE_SIZE=1024*1024*30):
            response = self.client.post(
                reverse('upload_images_preview_ajax', args=[self.source.pk]),
                post_dict,
            )

        response_json = response.json()
        self.assertDictEqual(
            response_json,
            dict(statuses=[dict(error="Exceeds size limit of 30.00 MB")])
        )

    def test_upload_max_memory_size(self):
        """Exceeding the upload max memory size setting should be okay."""
        image_file = sample_image_as_file(
            '1.png', image_options=dict(width=600, height=450),
        )

        self.client.force_login(self.user)
        post_dict = dict(file=image_file, name=image_file.name)

        # Use an upload max memory size of 200 bytes; as long as the image has
        # some color variation, no way it'll be smaller than that
        with self.settings(FILE_UPLOAD_MAX_MEMORY_SIZE=200):
            response = self.client.post(
                reverse('upload_images_ajax', args=[self.source.pk]),
                post_dict,
            )

        response_json = response.json()
        self.assertEqual(response_json['success'], True)
        image_id = response_json['image_id']
        image = Image.objects.get(pk=image_id)
        self.assertEqual(image.metadata.name, '1.png')
