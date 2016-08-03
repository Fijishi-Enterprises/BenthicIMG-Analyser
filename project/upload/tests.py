import csv
import datetime
import json
from io import BytesIO
import re

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.urlresolvers import reverse
from django.utils import timezone

from accounts.utils import get_imported_user
from annotations.model_utils import AnnotationAreaUtils
from annotations.models import Annotation
from images.model_utils import PointGen
from images.models import Image, Point
from lib.test_utils import ClientTest, sample_image_as_file, create_sample_image


class UploadImagePreviewTest(ClientTest):
    """
    Test the upload-image preview view.
    """
    @classmethod
    def setUpTestData(cls):
        super(UploadImagePreviewTest, cls).setUpTestData()

        cls.user = cls.create_user()
        cls.source = cls.create_source(cls.user)

        cls.img1 = cls.upload_image_new(
            cls.user, cls.source, image_options=dict(filename='1.png'))
        cls.img2 = cls.upload_image_new(
            cls.user, cls.source, image_options=dict(filename='2.png'))

    def test_no_dupe(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse(
                'image_upload_preview_ajax',
                kwargs={'source_id': self.source.pk}),
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
            reverse(
                'image_upload_preview_ajax',
                kwargs={'source_id': self.source.pk}),
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
            reverse(
                'image_upload_preview_ajax',
                kwargs={'source_id': self.source.pk}),
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
            reverse('image_upload_ajax', kwargs={'source_id': self.source.pk}),
            dict(file=sample_image_as_file('1.png'))
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
            reverse('image_upload_ajax', kwargs={'source_id': self.source.pk}),
            dict(file=sample_image_as_file('A.jpg'))
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
        post_dict = dict(file=image_file)
        response = self.client.post(
            reverse('image_upload_ajax', kwargs={'source_id': self.source.pk}),
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

        # cm height.
        self.assertEqual(
            img.metadata.height_in_cm, img.source.image_height_in_cm)


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
            reverse('image_upload_ajax', kwargs={'source_id': self.source.pk}),
            dict(file=ContentFile('here is some text', name='1.txt')),
        )

        response_json = response.json()
        self.assertDictEqual(
            response_json,
            dict(error=(
                "The file is either a corrupt image,"
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
            reverse('image_upload_ajax', kwargs={'source_id': self.source.pk}),
            dict(file=bmp_file),
        )

        response_json = response.json()
        self.assertDictEqual(
            response_json,
            dict(error=("This image file format isn't supported."))
        )

    def test_empty_file(self):
        """0-byte file. Should get an error."""
        self.client.force_login(self.user)
        response = self.client.post(
            reverse('image_upload_ajax', kwargs={'source_id': self.source.pk}),
            dict(file=ContentFile(bytes(), name='1.png')),
        )

        response_json = response.json()
        self.assertDictEqual(
            response_json,
            dict(error=("The submitted file is empty."))
        )

    def test_max_image_dimensions_1(self):
        """Should check the max image width."""
        image_file = sample_image_as_file(
            '1.png', image_options=dict(width=600, height=450),
        )

        self.client.force_login(self.user)
        post_dict = dict(file=image_file)
        with self.settings(IMAGE_UPLOAD_MAX_DIMENSIONS=(599, 1000)):
            response = self.client.post(
                reverse(
                    'image_upload_ajax', kwargs={'source_id': self.source.pk}),
                post_dict,
            )

        response_json = response.json()
        self.assertDictEqual(
            response_json,
            dict(error=("Ensure the image dimensions are at most 599 x 1000."))
        )

    def test_max_image_dimensions_2(self):
        """Should check the max image height."""
        image_file = sample_image_as_file(
            '1.png', image_options=dict(width=600, height=450),
        )

        self.client.force_login(self.user)
        post_dict = dict(file=image_file)
        with self.settings(IMAGE_UPLOAD_MAX_DIMENSIONS=(1000, 449)):
            response = self.client.post(
                reverse(
                    'image_upload_ajax', kwargs={'source_id': self.source.pk}),
                post_dict,
            )

        response_json = response.json()
        self.assertDictEqual(
            response_json,
            dict(error=("Ensure the image dimensions are at most 1000 x 449."))
        )

    def test_max_filesize(self):
        """Should check the max filesize in the upload preview."""
        self.client.force_login(self.user)

        post_dict = dict(file_info=json.dumps(
            [dict(filename='1.png', size=1024*1024*1024)]
        ))

        with self.settings(IMAGE_UPLOAD_MAX_FILE_SIZE=1024*1024*30):
            response = self.client.post(
                reverse(
                    'image_upload_preview_ajax',
                    kwargs={'source_id': self.source.pk}),
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
        post_dict = dict(file=image_file)

        # Use an upload max memory size of 200 bytes; as long as the image has
        # some color variation, no way it'll be smaller than that
        with self.settings(FILE_UPLOAD_MAX_MEMORY_SIZE=200):
            response = self.client.post(
                reverse(
                    'image_upload_ajax', kwargs={'source_id': self.source.pk}),
                post_dict,
            )

        response_json = response.json()
        self.assertEqual(response_json['success'], True)
        image_id = response_json['image_id']
        image = Image.objects.get(pk=image_id)
        self.assertEqual(image.metadata.name, '1.png')


class UploadMetadataTest(ClientTest):
    """
    Metadata upload and preview.
    """
    @classmethod
    def setUpTestData(cls):
        super(UploadMetadataTest, cls).setUpTestData()

        cls.user = cls.create_user()
        cls.source = cls.create_source(cls.user)

        cls.source.key1 = 'Site'
        cls.source.key2 = 'Habitat'
        cls.source.key3 = 'Transect'
        cls.source.image_height_in_cm = 50
        cls.source.save()

        cls.img1 = cls.upload_image_new(
            cls.user, cls.source, image_options=dict(filename='1.png'))
        cls.img2 = cls.upload_image_new(
            cls.user, cls.source, image_options=dict(filename='2.png'))

        cls.standard_column_order = [
            'Name', 'Date', 'Site', 'Habitat', 'Transect', 'Aux4', 'Aux5',
            'Height (cm)', 'Latitude', 'Longitude', 'Depth',
            'Camera', 'Photographer', 'Water quality',
            'Strobes', 'Framing gear used', 'White balance card', 'Comments',
        ]

    def preview(self, csv_file):
        return self.client.post(
            reverse(
                'upload_metadata_preview_ajax',
                kwargs={'source_id': self.source.pk}),
            {'csv_file': csv_file},
        )

    def upload(self):
        return self.client.post(
            reverse(
                'upload_metadata_ajax',
                kwargs={'source_id': self.source.pk}),
        )

    def test_starting_from_blank_metadata(self):
        """
        Everything except height (cm) starts blank and has nothing
        to be replaced.
        """
        self.client.force_login(self.user)

        with BytesIO() as stream:
            writer = csv.DictWriter(stream, self.standard_column_order)
            writer.writeheader()
            writer.writerow({
                'Name': '1.png',
                'Date': '2016-07-18',
                'Site': 'SiteA',
                'Habitat': 'Fringing Reef',
                'Transect': '2-4',
                'Aux4': 'Q5',
                'Aux5': '28',
                'Height (cm)': '50',
                'Latitude': '20.18',
                'Longitude': '-59.64',
                'Depth': '30m',
                'Camera': 'Canon',
                'Photographer': 'Bob Doe',
                'Water quality': 'Mostly clear',
                'Strobes': '2x blue',
                'Framing gear used': 'FG-16',
                'White balance card': 'WB-03',
                'Comments': 'A bit off to the left from the transect line.',
            })
            writer.writerow({
                'Name': '2.png',
                'Date': '',
                'Site': 'SiteB',
                'Habitat': '10m out',
                'Transect': '',
                'Aux4': '',
                'Aux5': '',
                'Height (cm)': '50',
                'Latitude': '',
                'Longitude': '',
                'Depth': '',
                'Camera': 'Canon',
                'Photographer': '',
                'Water quality': '',
                'Strobes': '',
                'Framing gear used': 'FG-15',
                'White balance card': '',
                'Comments': '',
            })

            f = ContentFile(stream.getvalue(), name='A.csv')
            preview_response = self.preview(f)
            upload_response = self.upload()

        self.assertDictEqual(
            preview_response.json(),
            dict(
                success=True,
                previewTable=[
                    self.standard_column_order,
                    ['1.png', '2016-07-18', 'SiteA', 'Fringing Reef', '2-4',
                     'Q5', '28', '50', '20.18', '-59.64', '30m',
                     'Canon', 'Bob Doe', 'Mostly clear', '2x blue', 'FG-16',
                     'WB-03', 'A bit off to the left from the transect line.'],
                    ['2.png', '', 'SiteB', '10m out', '', '', '', '50',
                     '', '', '', 'Canon', '', '', '', 'FG-15', '', ''],
                ],
                previewDetails=dict(
                    numImages=2,
                    numFieldsReplaced=0,
                ),
            ),
        )

        self.assertDictEqual(upload_response.json(), dict(success=True))

        meta1 = Image.objects.get(pk=self.img1.pk).metadata
        self.assertEqual(meta1.name, '1.png')
        self.assertEqual(meta1.photo_date, datetime.date(2016,7,18))
        self.assertEqual(meta1.aux1, 'SiteA')
        self.assertEqual(meta1.aux2, 'Fringing Reef')
        self.assertEqual(meta1.aux3, '2-4')
        self.assertEqual(meta1.aux4, 'Q5')
        self.assertEqual(meta1.aux5, '28')
        self.assertEqual(meta1.height_in_cm, 50)
        self.assertEqual(meta1.latitude, '20.18')
        self.assertEqual(meta1.longitude, '-59.64')
        self.assertEqual(meta1.depth, '30m')
        self.assertEqual(meta1.camera, 'Canon')
        self.assertEqual(meta1.photographer, 'Bob Doe')
        self.assertEqual(meta1.water_quality, 'Mostly clear')
        self.assertEqual(meta1.strobes, '2x blue')
        self.assertEqual(meta1.framing, 'FG-16')
        self.assertEqual(meta1.balance, 'WB-03')
        self.assertEqual(
            meta1.comments, 'A bit off to the left from the transect line.')

        meta2 = Image.objects.get(pk=self.img2.pk).metadata
        self.assertEqual(meta2.name, '2.png')
        self.assertEqual(meta2.photo_date, None)
        self.assertEqual(meta2.aux1, 'SiteB')
        self.assertEqual(meta2.aux2, '10m out')
        self.assertEqual(meta2.aux3, '')
        self.assertEqual(meta2.aux4, '')
        self.assertEqual(meta2.aux5, '')
        self.assertEqual(meta2.height_in_cm, 50)
        self.assertEqual(meta2.latitude, '')
        self.assertEqual(meta2.longitude, '')
        self.assertEqual(meta2.depth, '')
        self.assertEqual(meta2.camera, 'Canon')
        self.assertEqual(meta2.photographer, '')
        self.assertEqual(meta2.water_quality, '')
        self.assertEqual(meta2.strobes, '')
        self.assertEqual(meta2.framing, 'FG-15')
        self.assertEqual(meta2.balance, '')
        self.assertEqual(meta2.comments, '')

    def test_some_same_metadata(self):
        """
        Some fields start out with non-blank values and
        the metadata specifies the same values for those fields.
        """
        self.client.force_login(self.user)

        meta1 = self.img1.metadata
        meta1.photo_date = datetime.date(2016,7,18)
        meta1.aux1 = 'SiteA'
        meta1.camera = 'Canon'
        meta1.save()

        with BytesIO() as stream:
            writer = csv.DictWriter(stream, self.standard_column_order)
            writer.writeheader()
            writer.writerow({
                'Name': '1.png',
                'Date': '2016-07-18',
                'Site': 'SiteA',
                'Habitat': 'Fringing Reef',
                'Transect': '2-4',
                'Aux4': 'Q5',
                'Aux5': '28',
                'Height (cm)': '50',
                'Latitude': '20.18',
                'Longitude': '-59.64',
                'Depth': '30m',
                'Camera': 'Canon',
                'Photographer': '',
                'Water quality': '',
                'Strobes': '',
                'Framing gear used': '',
                'White balance card': '',
                'Comments': '',
            })

            f = ContentFile(stream.getvalue(), name='A.csv')
            preview_response = self.preview(f)
            upload_response = self.upload()

        self.assertDictEqual(
            preview_response.json(),
            dict(
                success=True,
                previewTable=[
                    self.standard_column_order,
                    ['1.png', '2016-07-18', 'SiteA',
                     'Fringing Reef', '2-4',
                     'Q5', '28', '50', '20.18', '-59.64', '30m',
                     'Canon', '', '', '', '', '', ''],
                ],
                previewDetails=dict(
                    numImages=1,
                    numFieldsReplaced=0,
                ),
            ),
        )

        self.assertDictEqual(upload_response.json(), dict(success=True))

        meta1 = Image.objects.get(pk=self.img1.pk).metadata
        self.assertEqual(meta1.name, '1.png')
        self.assertEqual(meta1.photo_date, datetime.date(2016,7,18))
        self.assertEqual(meta1.aux1, 'SiteA')
        self.assertEqual(meta1.aux2, 'Fringing Reef')
        self.assertEqual(meta1.aux3, '2-4')
        self.assertEqual(meta1.aux4, 'Q5')
        self.assertEqual(meta1.aux5, '28')
        self.assertEqual(meta1.height_in_cm, 50)
        self.assertEqual(meta1.latitude, '20.18')
        self.assertEqual(meta1.longitude, '-59.64')
        self.assertEqual(meta1.depth, '30m')
        self.assertEqual(meta1.camera, 'Canon')
        self.assertEqual(meta1.photographer, '')
        self.assertEqual(meta1.water_quality, '')
        self.assertEqual(meta1.strobes, '')
        self.assertEqual(meta1.framing, '')
        self.assertEqual(meta1.balance, '')
        self.assertEqual(meta1.comments, '')

    def test_some_replaced_metadata(self):
        """
        Some fields get their non-blank values replaced
        with different values (blank or non-blank).
        """
        self.client.force_login(self.user)

        meta1 = self.img1.metadata
        meta1.photo_date = datetime.date(2014,2,27)
        meta1.aux1 = 'SiteC'
        meta1.camera = 'Nikon'
        meta1.save()

        with BytesIO() as stream:
            writer = csv.DictWriter(stream, self.standard_column_order)
            writer.writeheader()
            writer.writerow({
                'Name': '1.png',
                'Date': '2016-07-18',
                'Site': 'SiteA',
                'Habitat': 'Fringing Reef',
                'Transect': '2-4',
                'Aux4': 'Q5',
                'Aux5': '28',
                'Height (cm)': '',
                'Latitude': '20.18',
                'Longitude': '-59.64',
                'Depth': '30m',
                'Camera': '',
                'Photographer': '',
                'Water quality': '',
                'Strobes': '',
                'Framing gear used': '',
                'White balance card': '',
                'Comments': '',
            })

            f = ContentFile(stream.getvalue(), name='A.csv')
            preview_response = self.preview(f)
            upload_response = self.upload()

        self.assertDictEqual(
            preview_response.json(),
            dict(
                success=True,
                previewTable=[
                    self.standard_column_order,
                    ['1.png', ['2016-07-18', '2014-02-27'], ['SiteA', 'SiteC'],
                     'Fringing Reef', '2-4',
                     'Q5', '28', ['', '50'], '20.18', '-59.64', '30m',
                     ['', 'Nikon'], '', '', '', '', '', ''],
                ],
                previewDetails=dict(
                    numImages=1,
                    numFieldsReplaced=4,
                ),
            ),
        )

        self.assertDictEqual(upload_response.json(), dict(success=True))

        meta1 = Image.objects.get(pk=self.img1.pk).metadata
        self.assertEqual(meta1.name, '1.png')
        self.assertEqual(meta1.photo_date, datetime.date(2016,7,18))
        self.assertEqual(meta1.aux1, 'SiteA')
        self.assertEqual(meta1.aux2, 'Fringing Reef')
        self.assertEqual(meta1.aux3, '2-4')
        self.assertEqual(meta1.aux4, 'Q5')
        self.assertEqual(meta1.aux5, '28')
        self.assertEqual(meta1.height_in_cm, None)
        self.assertEqual(meta1.latitude, '20.18')
        self.assertEqual(meta1.longitude, '-59.64')
        self.assertEqual(meta1.depth, '30m')
        self.assertEqual(meta1.camera, '')
        self.assertEqual(meta1.photographer, '')
        self.assertEqual(meta1.water_quality, '')
        self.assertEqual(meta1.strobes, '')
        self.assertEqual(meta1.framing, '')
        self.assertEqual(meta1.balance, '')
        self.assertEqual(meta1.comments, '')

    def test_skipped_fields(self):
        """
        The CSV doesn't have to cover every possible field in its columns.
        Excluded fields should have their metadata untouched.
        """
        self.client.force_login(self.user)

        meta1 = self.img1.metadata
        meta1.photo_date = datetime.date(2014,2,27)
        meta1.aux1 = 'SiteC'
        meta1.camera = 'Nikon'
        meta1.save()

        column_names = ['Name', 'Site', 'Habitat', 'Transect']

        with BytesIO() as stream:
            writer = csv.DictWriter(stream, column_names)
            writer.writeheader()
            writer.writerow({
                'Name': '1.png',
                'Site': 'SiteA',
                'Habitat': 'Fringing Reef',
                'Transect': '2-4',
            })

            f = ContentFile(stream.getvalue(), name='A.csv')
            preview_response = self.preview(f)
            upload_response = self.upload()

        self.assertDictEqual(
            preview_response.json(),
            dict(
                success=True,
                previewTable=[
                    column_names,
                    ['1.png', ['SiteA', 'SiteC'],
                     'Fringing Reef', '2-4'],
                ],
                previewDetails=dict(
                    numImages=1,
                    numFieldsReplaced=1,
                ),
            ),
        )

        self.assertDictEqual(upload_response.json(), dict(success=True))

        meta1 = Image.objects.get(pk=self.img1.pk).metadata
        self.assertEqual(meta1.name, '1.png')
        self.assertEqual(meta1.photo_date, datetime.date(2014,2,27))
        self.assertEqual(meta1.aux1, 'SiteA')
        self.assertEqual(meta1.aux2, 'Fringing Reef')
        self.assertEqual(meta1.aux3, '2-4')
        self.assertEqual(meta1.height_in_cm, 50)
        self.assertEqual(meta1.camera, 'Nikon')

    def test_skipped_csv_columns(self):
        """
        The CSV can have column names that we don't recognize. Those columns
        will just be ignored.
        """
        self.client.force_login(self.user)

        column_names = ['Name', 'Site', 'Time of day', 'Habitat', 'Transect']

        with BytesIO() as stream:
            writer = csv.DictWriter(stream, column_names)
            writer.writeheader()
            writer.writerow({
                'Name': '1.png',
                'Site': 'SiteA',
                'Time of day': 'Sunset',
                'Habitat': 'Fringing Reef',
                'Transect': '2-4',
            })

            f = ContentFile(stream.getvalue(), name='A.csv')
            preview_response = self.preview(f)
            upload_response = self.upload()

        self.assertDictEqual(
            preview_response.json(),
            dict(
                success=True,
                previewTable=[
                    ['Name', 'Site', 'Habitat', 'Transect'],
                    ['1.png', 'SiteA', 'Fringing Reef', '2-4'],
                ],
                previewDetails=dict(
                    numImages=1,
                    numFieldsReplaced=0,
                ),
            ),
        )

        self.assertDictEqual(upload_response.json(), dict(success=True))

        meta1 = Image.objects.get(pk=self.img1.pk).metadata
        self.assertEqual(meta1.name, '1.png')
        self.assertEqual(meta1.aux1, 'SiteA')
        self.assertEqual(meta1.aux2, 'Fringing Reef')
        self.assertEqual(meta1.aux3, '2-4')

    def test_skipped_filenames(self):
        """
        The CSV can have filenames that we don't recognize. Those rows
        will just be ignored.
        """
        self.client.force_login(self.user)

        column_names = ['Name', 'Site']

        with BytesIO() as stream:
            writer = csv.DictWriter(stream, column_names)
            writer.writeheader()
            writer.writerow({
                'Name': '1.png',
                'Site': 'SiteA',
            })
            writer.writerow({
                'Name': '10.png',
                'Site': 'SiteJ',
            })

            f = ContentFile(stream.getvalue(), name='A.csv')
            preview_response = self.preview(f)
            upload_response = self.upload()

        self.assertDictEqual(
            preview_response.json(),
            dict(
                success=True,
                previewTable=[
                    ['Name', 'Site'],
                    ['1.png', 'SiteA'],
                ],
                previewDetails=dict(
                    numImages=1,
                    numFieldsReplaced=0,
                ),
            ),
        )

        self.assertDictEqual(upload_response.json(), dict(success=True))

        meta1 = Image.objects.get(pk=self.img1.pk).metadata
        self.assertEqual(meta1.name, '1.png')
        self.assertEqual(meta1.aux1, 'SiteA')

    def test_columns_different_order(self):
        """
        The CSV columns can be in a different order.
        """
        self.client.force_login(self.user)

        column_names = ['Transect', 'Site', 'Name']

        with BytesIO() as stream:
            writer = csv.DictWriter(stream, column_names)
            writer.writeheader()
            writer.writerow({
                'Transect': '2-4',
                'Site': 'SiteA',
                'Name': '1.png',
            })

            f = ContentFile(stream.getvalue(), name='A.csv')
            preview_response = self.preview(f)
            upload_response = self.upload()

        self.assertDictEqual(
            preview_response.json(),
            dict(
                success=True,
                previewTable=[
                    column_names,
                    ['2-4', 'SiteA', '1.png'],
                ],
                previewDetails=dict(
                    numImages=1,
                    numFieldsReplaced=0,
                ),
            ),
        )

        self.assertDictEqual(upload_response.json(), dict(success=True))

        meta1 = Image.objects.get(pk=self.img1.pk).metadata
        self.assertEqual(meta1.name, '1.png')
        self.assertEqual(meta1.aux1, 'SiteA')
        self.assertEqual(meta1.aux3, '2-4')

    def test_columns_different_case(self):
        """
        The CSV column names can use different upper/lower case and still
        be matched to the metadata field labels.
        """
        self.client.force_login(self.user)

        column_names = ['TRANSECT', 'site', 'NaMe']

        with BytesIO() as stream:
            writer = csv.DictWriter(stream, column_names)
            writer.writeheader()
            writer.writerow({
                'TRANSECT': '2-4',
                'site': 'SiteA',
                'NaMe': '1.png',
            })

            f = ContentFile(stream.getvalue(), name='A.csv')
            preview_response = self.preview(f)
            upload_response = self.upload()

        self.assertDictEqual(
            preview_response.json(),
            dict(
                success=True,
                previewTable=[
                    ['Transect', 'Site', 'Name'],
                    ['2-4', 'SiteA', '1.png'],
                ],
                previewDetails=dict(
                    numImages=1,
                    numFieldsReplaced=0,
                ),
            ),
        )

        self.assertDictEqual(upload_response.json(), dict(success=True))

        meta1 = Image.objects.get(pk=self.img1.pk).metadata
        self.assertEqual(meta1.name, '1.png')
        self.assertEqual(meta1.aux1, 'SiteA')
        self.assertEqual(meta1.aux3, '2-4')

    def test_dupe_column_names(self):
        """
        Two CSV columns have the same name. Shouldn't get a server error.
        (Arbitrarily, the later column will take precedence).
        """
        self.client.force_login(self.user)

        column_names = ['Name', 'Latitude', 'LATITUDE']

        with BytesIO() as stream:
            writer = csv.DictWriter(stream, column_names)
            writer.writeheader()
            writer.writerow({
                'Name': '1.png',
                'Latitude': '24.08',
                'LATITUDE': '42.67',
            })

            f = ContentFile(stream.getvalue(), name='A.csv')
            preview_response = self.preview(f)
            upload_response = self.upload()

        self.assertDictEqual(
            preview_response.json(),
            dict(
                success=True,
                previewTable=[
                    ['Name', 'Latitude'],
                    ['1.png', '42.67'],
                ],
                previewDetails=dict(
                    numImages=1,
                    numFieldsReplaced=0,
                ),
            ),
        )

        self.assertDictEqual(upload_response.json(), dict(success=True))

        meta1 = Image.objects.get(pk=self.img1.pk).metadata
        self.assertEqual(meta1.name, '1.png')
        self.assertEqual(meta1.latitude, '42.67')


class UploadMetadataMultipleSourcesTest(ClientTest):
    """
    Test involving multiple sources.
    """
    @classmethod
    def setUpTestData(cls):
        super(UploadMetadataMultipleSourcesTest, cls).setUpTestData()

        cls.user = cls.create_user()
        cls.source = cls.create_source(cls.user)
        cls.source2 = cls.create_source(cls.user)

        cls.img1_s1 = cls.upload_image_new(
            cls.user, cls.source, image_options=dict(filename='1.png'))
        cls.img1_s2 = cls.upload_image_new(
            cls.user, cls.source2, image_options=dict(filename='1.png'))
        cls.img2_s2 = cls.upload_image_new(
            cls.user, cls.source2, image_options=dict(filename='2.png'))

    def preview1(self, csv_file):
        return self.client.post(
            reverse(
                'upload_metadata_preview_ajax',
                kwargs={'source_id': self.source.pk}),
            {'csv_file': csv_file},
        )

    def upload1(self):
        return self.client.post(
            reverse(
                'upload_metadata_ajax',
                kwargs={'source_id': self.source.pk}),
        )

    def preview2(self, csv_file):
        return self.client.post(
            reverse(
                'upload_metadata_preview_ajax',
                kwargs={'source_id': self.source2.pk}),
            {'csv_file': csv_file},
        )

    def upload2(self):
        return self.client.post(
            reverse(
                'upload_metadata_ajax',
                kwargs={'source_id': self.source2.pk}),
        )

    def test_other_sources_unaffected(self):
        """
        We shouldn't touch images of other sources which happen to have
        the same image names.
        """
        self.client.force_login(self.user)

        column_names = ['Name', 'Aux1']

        # Upload to source 2
        with BytesIO() as stream:
            writer = csv.DictWriter(stream, column_names)
            writer.writeheader()
            writer.writerow({
                'Name': '1.png',
                'Aux1': 'SiteA',
            })
            writer.writerow({
                'Name': '2.png',
                'Aux1': 'SiteB',
            })

            f = ContentFile(stream.getvalue(), name='A.csv')
            self.preview2(f)
            self.upload2()

        # Upload to source 1
        with BytesIO() as stream:
            writer = csv.DictWriter(stream, column_names)
            writer.writeheader()
            writer.writerow({
                'Name': '1.png',
                'Aux1': 'SiteC',
            })
            writer.writerow({
                'Name': '2.png',
                'Aux1': 'SiteD',
            })

            f = ContentFile(stream.getvalue(), name='B.csv')
            preview_response = self.preview1(f)
            upload_response = self.upload1()

        # Check source 1 responses

        self.assertDictEqual(
            preview_response.json(),
            dict(
                success=True,
                previewTable=[
                    column_names,
                    ['1.png', 'SiteC'],
                ],
                previewDetails=dict(
                    numImages=1,
                    numFieldsReplaced=0,
                ),
            ),
        )

        self.assertDictEqual(upload_response.json(), dict(success=True))

        # Check source 1 objects

        meta1_s1 = self.img1_s1.metadata
        self.assertEqual(meta1_s1.name, '1.png')
        self.assertEqual(meta1_s1.aux1, 'SiteC')

        # Check source 2 objects

        meta1_s2 = self.img1_s2.metadata
        meta2_s2 = self.img2_s2.metadata
        self.assertEqual(meta1_s2.name, '1.png')
        self.assertEqual(meta1_s2.aux1, 'SiteA')
        self.assertEqual(meta2_s2.name, '2.png')
        self.assertEqual(meta2_s2.aux1, 'SiteB')


class UploadMetadataPreviewTest(ClientTest):
    """
    Tests only pertaining to metadata preview.
    """
    @classmethod
    def setUpTestData(cls):
        super(UploadMetadataPreviewTest, cls).setUpTestData()

        cls.user = cls.create_user()
        cls.source = cls.create_source(cls.user)

        cls.source.key1 = 'Site'
        cls.source.save()

        cls.img1 = cls.upload_image_new(
            cls.user, cls.source, image_options=dict(filename='1.png'))
        cls.img2 = cls.upload_image_new(
            cls.user, cls.source, image_options=dict(filename='2.png'))
        cls.img3 = cls.upload_image_new(
            cls.user, cls.source, image_options=dict(filename='3.png'))
        cls.img4 = cls.upload_image_new(
            cls.user, cls.source, image_options=dict(filename='4.png'))
        cls.img5 = cls.upload_image_new(
            cls.user, cls.source, image_options=dict(filename='5.png'))
        cls.img6 = cls.upload_image_new(
            cls.user, cls.source, image_options=dict(filename='6.png'))
        cls.img7 = cls.upload_image_new(
            cls.user, cls.source, image_options=dict(filename='7.png'))
        cls.img8 = cls.upload_image_new(
            cls.user, cls.source, image_options=dict(filename='8.png'))
        cls.img9 = cls.upload_image_new(
            cls.user, cls.source, image_options=dict(filename='9.png'))
        cls.img10 = cls.upload_image_new(
            cls.user, cls.source, image_options=dict(filename='10.png'))

    def preview(self, csv_file):
        return self.client.post(
            reverse(
                'upload_metadata_preview_ajax',
                kwargs={'source_id': self.source.pk}),
            {'csv_file': csv_file},
        )

    def test_row_order_preserved_in_preview_table(self):
        """
        The CSV row order should be the same as the row order
        in the preview table.
        """
        self.client.force_login(self.user)

        column_names = ['Name', 'Site']

        with BytesIO() as stream:
            writer = csv.DictWriter(stream, column_names)
            writer.writeheader()
            writer.writerow({'Name': '5.png', 'Site': 'SiteE'})
            writer.writerow({'Name': '1.png', 'Site': 'SiteA'})
            writer.writerow({'Name': '2.png', 'Site': 'SiteB'})
            writer.writerow({'Name': '6.png', 'Site': 'SiteF'})
            writer.writerow({'Name': '10.png', 'Site': 'SiteJ'})
            writer.writerow({'Name': '4.png', 'Site': 'SiteD'})
            writer.writerow({'Name': '7.png', 'Site': 'SiteG'})
            writer.writerow({'Name': '8.png', 'Site': 'SiteH'})
            writer.writerow({'Name': '9.png', 'Site': 'SiteI'})
            writer.writerow({'Name': '3.png', 'Site': 'SiteC'})

            f = ContentFile(stream.getvalue(), name='A.csv')
            preview_response = self.preview(f)

        self.assertDictEqual(
            preview_response.json(),
            dict(
                success=True,
                previewTable=[
                    column_names,
                    ['5.png', 'SiteE'],
                    ['1.png', 'SiteA'],
                    ['2.png', 'SiteB'],
                    ['6.png', 'SiteF'],
                    ['10.png', 'SiteJ'],
                    ['4.png', 'SiteD'],
                    ['7.png', 'SiteG'],
                    ['8.png', 'SiteH'],
                    ['9.png', 'SiteI'],
                    ['3.png', 'SiteC'],
                ],
                previewDetails=dict(
                    numImages=10,
                    numFieldsReplaced=0,
                ),
            ),
        )


class UploadMetadataErrorTest(ClientTest):
    """
    Metadata upload, error cases.
    """
    @classmethod
    def setUpTestData(cls):
        super(UploadMetadataErrorTest, cls).setUpTestData()

        cls.user = cls.create_user()
        cls.source = cls.create_source(cls.user)

        cls.img1 = cls.upload_image_new(
            cls.user, cls.source, image_options=dict(filename='1.png'))
        cls.img2 = cls.upload_image_new(
            cls.user, cls.source, image_options=dict(filename='2.png'))

        cls.standard_column_order = [
            'Name', 'Date', 'Aux1', 'Aux2', 'Aux3', 'Aux4', 'Aux5',
            'Height (cm)', 'Latitude', 'Longitude', 'Depth',
            'Camera', 'Photographer', 'Water quality',
            'Strobes', 'Framing gear used', 'White balance card', 'Comments',
        ]

    def preview(self, csv_file):
        return self.client.post(
            reverse(
                'upload_metadata_preview_ajax',
                kwargs={'source_id': self.source.pk}),
            {'csv_file': csv_file},
        )

    def upload(self):
        return self.client.post(
            reverse(
                'upload_metadata_ajax',
                kwargs={'source_id': self.source.pk})
        )

    def test_expired_session(self):
        """
        The session variable is cleared between preview and upload.
        """
        self.client.force_login(self.user)

        column_names = ['Name', 'Aux1']

        with BytesIO() as stream:
            writer = csv.DictWriter(stream, column_names)
            writer.writeheader()
            writer.writerow({
                'Name': '1.png',
                'Aux1': 'SiteA',
            })

            f = ContentFile(stream.getvalue(), name='A.csv')
            self.preview(f)

        # Clear the session data
        #
        # "Be careful: To modify the session and then save it,
        # it must be stored in a variable first (because a new SessionStore
        # is created every time this property is accessed)"
        # http://stackoverflow.com/a/4454671/
        session = self.client.session
        session.pop('csv_metadata')
        session.save()

        upload_response = self.upload()

        self.assertDictEqual(
            upload_response.json(),
            dict(error=(
                "We couldn't find the expected data in your session."
                " Please try loading this page again. If the problem persists,"
                " contact a site admin."
            )),
        )


class UploadMetadataPreviewErrorTest(ClientTest):
    """
    Metadata upload preview, error cases (mainly related to CSV content).
    """
    @classmethod
    def setUpTestData(cls):
        super(UploadMetadataPreviewErrorTest, cls).setUpTestData()

        cls.user = cls.create_user()
        cls.source = cls.create_source(cls.user)

        cls.img1 = cls.upload_image_new(
            cls.user, cls.source, image_options=dict(filename='1.png'))
        cls.img2 = cls.upload_image_new(
            cls.user, cls.source, image_options=dict(filename='2.png'))

        cls.standard_column_order = [
            'Name', 'Date', 'Aux1', 'Aux2', 'Aux3', 'Aux4', 'Aux5',
            'Height (cm)', 'Latitude', 'Longitude', 'Depth',
            'Camera', 'Photographer', 'Water quality',
            'Strobes', 'Framing gear used', 'White balance card', 'Comments',
        ]

    def preview(self, csv_file):
        return self.client.post(
            reverse(
                'upload_metadata_preview_ajax',
                kwargs={'source_id': self.source.pk}),
            {'csv_file': csv_file},
        )

    def test_dupe_field_labels_1(self):
        """
        An aux. metadata field has the same label (non case sensitive)
        as a default metadata field.

        Gets an error even if this metadata field is not involved in the
        import.
        (It behaves this way just to make implementing the check simpler.)
        """
        self.client.force_login(self.user)

        self.source.key2 = 'CAMERA'
        self.source.save()

        column_names = ['Name', 'Aux1']

        with BytesIO() as stream:
            writer = csv.DictWriter(stream, column_names)
            writer.writeheader()
            writer.writerow({
                'Name': '1.png',
                'Aux1': 'SiteA',
            })

            f = ContentFile(stream.getvalue(), name='A.csv')
            preview_response = self.preview(f)

        self.assertDictEqual(
            preview_response.json(),
            dict(
                error=(
                    "More than one metadata field uses the label 'camera'."
                    " Your auxiliary fields' names must be unique"
                    " and different from the default metadata fields."
                ),
            ),
        )

    def test_dupe_field_labels_2(self):
        """
        Two aux. metadata fields have the same label.
        """
        self.client.force_login(self.user)

        self.source.key1 = 'Site'
        self.source.key2 = 'site'
        self.source.save()

        column_names = ['Name', 'Site']

        with BytesIO() as stream:
            writer = csv.DictWriter(stream, column_names)
            writer.writeheader()
            writer.writerow({
                'Name': '1.png',
                'Site': 'SiteA',
            })

            f = ContentFile(stream.getvalue(), name='A.csv')
            preview_response = self.preview(f)

        self.assertDictEqual(
            preview_response.json(),
            dict(
                error=(
                    "More than one metadata field uses the label 'site'."
                    " Your auxiliary fields' names must be unique"
                    " and different from the default metadata fields."
                ),
            ),
        )

    def test_dupe_row_filenames(self):
        """
        Two CSV rows have the same filename.
        """
        self.client.force_login(self.user)

        column_names = ['Name', 'Aux1']

        with BytesIO() as stream:
            writer = csv.DictWriter(stream, column_names)
            writer.writeheader()
            writer.writerow({
                'Name': '1.png',
                'Aux1': 'SiteA',
            })
            writer.writerow({
                'Name': '1.png',
                'Aux1': 'SiteA',
            })

            f = ContentFile(stream.getvalue(), name='A.csv')
            preview_response = self.preview(f)

        self.assertDictEqual(
            preview_response.json(),
            dict(
                error=(
                    "More than one row with the same image name: 1.png"
                ),
            ),
        )

    def test_no_specified_images_found_in_source(self):
        """
        No CSV rows have a filename that can be found in the source.
        """
        self.client.force_login(self.user)

        column_names = ['Name', 'Aux1']

        with BytesIO() as stream:
            writer = csv.DictWriter(stream, column_names)
            writer.writeheader()
            writer.writerow({
                'Name': '3.png',
                'Aux1': 'SiteA',
            })

            f = ContentFile(stream.getvalue(), name='A.csv')
            preview_response = self.preview(f)

        self.assertDictEqual(
            preview_response.json(),
            dict(
                error=(
                    "No matching filenames found in the source"
                ),
            ),
        )

    def test_no_name_column(self):
        """
        No CSV columns correspond to the name field.
        """
        self.client.force_login(self.user)

        column_names = ['Aux1', 'Aux2']

        with BytesIO() as stream:
            writer = csv.DictWriter(stream, column_names)
            writer.writeheader()
            writer.writerow({
                'Aux1': 'SiteA',
                'Aux2': 'Fringing Reef',
            })

            f = ContentFile(stream.getvalue(), name='A.csv')
            preview_response = self.preview(f)

        self.assertDictEqual(
            preview_response.json(),
            dict(
                error=(
                    "CSV must have a column called Name"
                ),
            ),
        )

    def test_no_recognized_non_name_column(self):
        """
        No CSV columns correspond to metadata fields besides the name field,
        and thus no metadata could be found.
        """
        self.client.force_login(self.user)

        column_names = ['Name', 'Time of day']

        with BytesIO() as stream:
            writer = csv.DictWriter(stream, column_names)
            writer.writeheader()
            writer.writerow({
                'Name': '1.png',
                'Time of day': 'Sunset',
            })

            f = ContentFile(stream.getvalue(), name='A.csv')
            preview_response = self.preview(f)

        self.assertDictEqual(
            preview_response.json(),
            dict(error=(
                "CSV must have at least one metadata column other than Name"
            )),
        )

    def test_invalid_metadata_value(self):
        """
        One of the metadata values is invalid.
        """
        self.client.force_login(self.user)

        column_names = ['Name', 'Date']

        with BytesIO() as stream:
            writer = csv.DictWriter(stream, column_names)
            writer.writeheader()
            writer.writerow({
                'Name': '1.png',
                'Date': '2015-02-29',  # Nonexistent date
            })

            f = ContentFile(stream.getvalue(), name='A.csv')
            preview_response = self.preview(f)

        self.assertDictEqual(
            preview_response.json(),
            dict(error=("(1.png - Date) Enter a valid date.")),
        )


class UploadMetadataPreviewFormatTest(ClientTest):
    """
    Metadata upload preview, special cases or error cases with CSV formats.
    """
    @classmethod
    def setUpTestData(cls):
        super(UploadMetadataPreviewFormatTest, cls).setUpTestData()

        cls.user = cls.create_user()
        cls.source = cls.create_source(cls.user)

        cls.img1 = cls.upload_image_new(
            cls.user, cls.source, image_options=dict(filename='1.png'))
        cls.img2 = cls.upload_image_new(
            cls.user, cls.source, image_options=dict(filename='2.png'))

    def preview(self, csv_file):
        return self.client.post(
            reverse(
                'upload_metadata_preview_ajax',
                kwargs={'source_id': self.source.pk}),
            {'csv_file': csv_file},
        )

    def test_cr_only_newlines(self):
        """
        Tolerate carriage-return-only newlines in the CSV (old Mac style).
        """
        self.client.force_login(self.user)

        content = (
            'Name,Aux1'
            '\r1.png,SiteA'
        )
        f = ContentFile(content, name='A.csv')
        preview_response = self.preview(f)

        self.assertDictEqual(
            preview_response.json(),
            dict(
                success=True,
                previewTable=[
                    ['Name', 'Aux1'],
                    ['1.png', 'SiteA'],
                ],
                previewDetails=dict(
                    numImages=1,
                    numFieldsReplaced=0,
                ),
            ),
        )

    def test_utf8_chars(self):
        """
        Tolerate non-ASCII UTF-8 characters in the CSV.
        """
        # TODO: Not sure how to make this work with Python 2 and its CSV module
        # (getting them to work with non-ASCII is a known pain).
        # But it seems the use case hasn't come up in practice yet, so let's
        # defer this until (1) it comes up in practice, or
        # (2) we upgrade to Python 3.
        return

        self.client.force_login(self.user)

        content = (
            'Name,Aux1'
            '\r1.png,\xe5\x9c\xb0\xe7\x82\xb9A'
        )
        f = ContentFile(content, name='A.csv')
        preview_response = self.preview(f)

        self.assertDictEqual(
            preview_response.json(),
            dict(
                success=True,
                previewTable=[
                    ['Name', 'Aux1'],
                    ['1.png', '\xe5\x9c\xb0\xe7\x82\xb9A'],
                ],
                previewDetails=dict(
                    numImages=1,
                    numFieldsReplaced=0,
                ),
            ),
        )

    def test_utf8_bom_char(self):
        """
        Tolerate UTF-8 BOM character at the start of the CSV.
        """
        self.client.force_login(self.user)

        content = (
            '\xef\xbb\xbfName,Aux1'
            '\n1.png,SiteA'
        )
        f = ContentFile(content, name='A.csv')
        preview_response = self.preview(f)

        self.assertDictEqual(
            preview_response.json(),
            dict(
                success=True,
                previewTable=[
                    ['Name', 'Aux1'],
                    ['1.png', 'SiteA'],
                ],
                previewDetails=dict(
                    numImages=1,
                    numFieldsReplaced=0,
                ),
            ),
        )

    def test_extra_quotes(self):
        """
        Strip "surrounding quotes" around CSV values. This is the most common
        text delimiter for CSVs, used to enclose cell values containing commas.
        Depending on how you save your CSV, your program might auto-add quotes
        even in the absence of commas.
        """
        self.client.force_login(self.user)

        content = (
            'Name,Aux1'
            '\n"1.png","SiteA,IsleB"'
        )
        f = ContentFile(content, name='A.csv')
        preview_response = self.preview(f)

        self.assertDictEqual(
            preview_response.json(),
            dict(
                success=True,
                previewTable=[
                    ['Name', 'Aux1'],
                    ['1.png', 'SiteA,IsleB'],
                ],
                previewDetails=dict(
                    numImages=1,
                    numFieldsReplaced=0,
                ),
            ),
        )

    def test_surrounding_whitespace(self):
        """
        Strip leading and trailing whitespace around CSV values.
        """
        self.client.force_login(self.user)

        content = (
            'Name,Aux1  '
            '\n 1.png\t,  SiteA '
        )
        f = ContentFile(content, name='A.csv')
        preview_response = self.preview(f)

        self.assertDictEqual(
            preview_response.json(),
            dict(
                success=True,
                previewTable=[
                    ['Name', 'Aux1'],
                    ['1.png', 'SiteA'],
                ],
                previewDetails=dict(
                    numImages=1,
                    numFieldsReplaced=0,
                ),
            ),
        )

    def test_non_csv(self):
        """
        Do at least basic detection of non-CSV files.
        """
        self.client.force_login(self.user)

        f = sample_image_as_file('A.jpg')
        preview_response = self.preview(f)

        self.assertDictEqual(
            preview_response.json(),
            dict(
                error="This file is not a CSV file.",
            ),
        )


class UploadAnnotationsTest(ClientTest):
    """
    Point/annotation upload and preview.
    """
    @classmethod
    def setUpTestData(cls):
        super(UploadAnnotationsTest, cls).setUpTestData()

        cls.user = cls.create_user()
        cls.source = cls.create_source(cls.user)
        labels = cls.create_labels(cls.user, cls.source, ['A', 'B'], 'Group1')
        cls.create_labelset(cls.user, cls.source, labels)

        cls.img1 = cls.upload_image_new(
            cls.user, cls.source,
            image_options=dict(filename='1.png', width=100, height=100))
        cls.img2 = cls.upload_image_new(
            cls.user, cls.source,
            image_options=dict(filename='2.png', width=100, height=100))
        cls.img3 = cls.upload_image_new(
            cls.user, cls.source,
            image_options=dict(filename='3.png', width=100, height=100))

    def preview(self, csv_file):
        return self.client.post(
            reverse(
                'upload_annotations_preview_ajax',
                kwargs={'source_id': self.source.pk}),
            {'csv_file': csv_file},
        )

    def upload(self):
        return self.client.post(
            reverse(
                'upload_annotations_ajax',
                kwargs={'source_id': self.source.pk}),
        )

    def test_points_only(self):
        """
        No annotations on specified points.
        """
        self.client.force_login(self.user)

        with BytesIO() as stream:
            writer = csv.writer(stream)
            writer.writerow(['Name', 'Row', 'Column'])
            writer.writerow(['1.png', 50, 50])
            writer.writerow(['1.png', 40, 60])
            writer.writerow(['1.png', 30, 70])
            writer.writerow(['1.png', 20, 80])
            writer.writerow(['1.png', 10, 90])
            writer.writerow(['2.png', 1, 1])
            writer.writerow(['2.png', 100, 100])
            writer.writerow(['2.png', 44, 44])

            f = ContentFile(stream.getvalue(), name='A.csv')
            preview_response = self.preview(f)
            upload_response = self.upload()

        self.assertDictEqual(
            preview_response.json(),
            dict(
                success=True,
                previewTable=[
                    dict(
                        name=self.img1.metadata.name,
                        link=reverse(
                            'annotation_tool',
                            kwargs=dict(image_id=self.img1.pk)),
                        createInfo="Will create 5 points, 0 annotations",
                    ),
                    dict(
                        name=self.img2.metadata.name,
                        link=reverse(
                            'annotation_tool',
                            kwargs=dict(image_id=self.img2.pk)),
                        createInfo="Will create 3 points, 0 annotations",
                    ),
                ],
                previewDetails=dict(
                    numImages=2,
                    totalPoints=8,
                    totalAnnotations=0,
                    numImagesWithExistingAnnotations=0,
                ),
            ),
        )

        self.assertDictEqual(upload_response.json(), dict(success=True))

        values_set = set(
            Point.objects.filter(image__in=[self.img1, self.img2]) \
            .values_list('row', 'column', 'point_number', 'image_id'))
        self.assertSetEqual(values_set, {
            (50, 50, 1, self.img1.pk),
            (40, 60, 2, self.img1.pk),
            (30, 70, 3, self.img1.pk),
            (20, 80, 4, self.img1.pk),
            (10, 90, 5, self.img1.pk),
            (1,  1,  1, self.img2.pk),
            (100, 100, 2, self.img2.pk),
            (44, 44, 3, self.img2.pk),
        })

        self.img1.refresh_from_db()
        self.assertEqual(
            self.img1.point_generation_method,
            PointGen.args_to_db_format(
                point_generation_type=PointGen.Types.IMPORTED,
                imported_number_of_points=5))
        self.assertEqual(
            self.img1.metadata.annotation_area,
            AnnotationAreaUtils.IMPORTED_STR)

        self.img2.refresh_from_db()
        self.assertEqual(
            self.img2.point_generation_method,
            PointGen.args_to_db_format(
                point_generation_type=PointGen.Types.IMPORTED,
                imported_number_of_points=3))
        self.assertEqual(
            self.img2.metadata.annotation_area,
            AnnotationAreaUtils.IMPORTED_STR)

    def test_with_all_annotations(self):
        """
        Annotations on all specified points.
        """
        self.client.force_login(self.user)

        with BytesIO() as stream:
            writer = csv.writer(stream)
            writer.writerow(['Name', 'Row', 'Column', 'Label'])
            writer.writerow(['1.png', 50, 50, 'A'])
            writer.writerow(['1.png', 40, 60, 'B'])
            writer.writerow(['2.png', 30, 70, 'A'])
            writer.writerow(['2.png', 20, 80, 'A'])

            f = ContentFile(stream.getvalue(), name='A.csv')
            preview_response = self.preview(f)
            upload_response = self.upload()

        self.assertDictEqual(
            preview_response.json(),
            dict(
                success=True,
                previewTable=[
                    dict(
                        name=self.img1.metadata.name,
                        link=reverse(
                            'annotation_tool',
                            kwargs=dict(image_id=self.img1.pk)),
                        createInfo="Will create 2 points, 2 annotations",
                    ),
                    dict(
                        name=self.img2.metadata.name,
                        link=reverse(
                            'annotation_tool',
                            kwargs=dict(image_id=self.img2.pk)),
                        createInfo="Will create 2 points, 2 annotations",
                    ),
                ],
                previewDetails=dict(
                    numImages=2,
                    totalPoints=4,
                    totalAnnotations=4,
                    numImagesWithExistingAnnotations=0,
                ),
            ),
        )

        self.assertDictEqual(upload_response.json(), dict(success=True))

        values_set = set(
            Point.objects.filter(image__in=[self.img1, self.img2]) \
            .values_list('row', 'column', 'point_number', 'image_id'))
        self.assertSetEqual(values_set, {
            (50, 50, 1, self.img1.pk),
            (40, 60, 2, self.img1.pk),
            (30, 70, 1, self.img2.pk),
            (20, 80, 2, self.img2.pk),
        })

        annotations = Annotation.objects.filter(
            image__in=[self.img1, self.img2])
        values_set = set(
            annotations.values_list('label__code', 'point_id', 'image_id'))
        self.assertSetEqual(values_set, {
            ('A', Point.objects.get(
                point_number=1, image=self.img1).pk, self.img1.pk),
            ('B', Point.objects.get(
                point_number=2, image=self.img1).pk, self.img1.pk),
            ('A', Point.objects.get(
                point_number=1, image=self.img2).pk, self.img2.pk),
            ('A', Point.objects.get(
                point_number=2, image=self.img2).pk, self.img2.pk),
        })
        for annotation in annotations:
            self.assertEqual(annotation.source.pk, self.source.pk)
            self.assertEqual(annotation.user.pk, get_imported_user().pk)
            self.assertEqual(annotation.robot_version, None)
            self.assertLess(
                self.source.create_date, annotation.annotation_date)

    def test_with_some_annotations(self):
        """
        Annotations on some specified points.
        """
        self.client.force_login(self.user)

        with BytesIO() as stream:
            writer = csv.writer(stream)
            writer.writerow(['Name', 'Row', 'Column', 'Label'])
            writer.writerow(['1.png', 50, 50, 'A'])
            writer.writerow(['1.png', 40, 60, 'B'])
            writer.writerow(['2.png', 30, 70, 'A'])
            writer.writerow(['2.png', 20, 80])
            writer.writerow(['3.png', 30, 70])
            writer.writerow(['3.png', 20, 80])

            f = ContentFile(stream.getvalue(), name='A.csv')
            preview_response = self.preview(f)
            upload_response = self.upload()

        self.assertDictEqual(
            preview_response.json(),
            dict(
                success=True,
                previewTable=[
                    dict(
                        name=self.img1.metadata.name,
                        link=reverse(
                            'annotation_tool',
                            kwargs=dict(image_id=self.img1.pk)),
                        createInfo="Will create 2 points, 2 annotations",
                    ),
                    dict(
                        name=self.img2.metadata.name,
                        link=reverse(
                            'annotation_tool',
                            kwargs=dict(image_id=self.img2.pk)),
                        createInfo="Will create 2 points, 1 annotations",
                    ),
                    dict(
                        name=self.img3.metadata.name,
                        link=reverse(
                            'annotation_tool',
                            kwargs=dict(image_id=self.img3.pk)),
                        createInfo="Will create 2 points, 0 annotations",
                    ),
                ],
                previewDetails=dict(
                    numImages=3,
                    totalPoints=6,
                    totalAnnotations=3,
                    numImagesWithExistingAnnotations=0,
                ),
            ),
        )

        self.assertDictEqual(upload_response.json(), dict(success=True))

        values_set = set(
            Point.objects.filter(
                image__in=[self.img1, self.img2, self.img3]) \
            .values_list('row', 'column', 'point_number', 'image_id'))
        self.assertSetEqual(values_set, {
            (50, 50, 1, self.img1.pk),
            (40, 60, 2, self.img1.pk),
            (30, 70, 1, self.img2.pk),
            (20, 80, 2, self.img2.pk),
            (30, 70, 1, self.img3.pk),
            (20, 80, 2, self.img3.pk),
        })

        annotations = Annotation.objects.filter(
            image__in=[self.img1, self.img2, self.img3])
        values_set = set(
            annotations.values_list('label__code', 'point_id', 'image_id'))
        self.assertSetEqual(values_set, {
            ('A', Point.objects.get(
                point_number=1, image=self.img1).pk, self.img1.pk),
            ('B', Point.objects.get(
                point_number=2, image=self.img1).pk, self.img1.pk),
            ('A', Point.objects.get(
                point_number=1, image=self.img2).pk, self.img2.pk),
        })
        for annotation in annotations:
            self.assertEqual(annotation.source.pk, self.source.pk)
            self.assertEqual(annotation.user.pk, get_imported_user().pk)
            self.assertEqual(annotation.robot_version, None)
            self.assertLess(
                self.source.create_date, annotation.annotation_date)

    def test_overwrite_annotations(self):
        """
        Save some annotations, then overwrite those with other annotations.
        """
        self.client.force_login(self.user)

        with BytesIO() as stream:
            writer = csv.writer(stream)
            writer.writerow(['Name', 'Row', 'Column', 'Label'])
            writer.writerow(['1.png', 50, 50, 'A'])
            writer.writerow(['1.png', 40, 60, 'B'])
            writer.writerow(['2.png', 30, 70, 'A'])
            writer.writerow(['2.png', 20, 80])
            writer.writerow(['3.png', 30, 70])
            writer.writerow(['3.png', 20, 80])

            f = ContentFile(stream.getvalue(), name='A.csv')
            self.preview(f)
            self.upload()

        with BytesIO() as stream:
            writer = csv.writer(stream)
            writer.writerow(['Name', 'Row', 'Column', 'Label'])
            writer.writerow(['1.png', 10, 10, 'A'])
            writer.writerow(['1.png', 20, 20, 'A'])
            writer.writerow(['2.png', 30, 30])
            writer.writerow(['2.png', 40, 40])
            writer.writerow(['3.png', 50, 50, 'A'])
            writer.writerow(['3.png', 60, 60, 'B'])

            f = ContentFile(stream.getvalue(), name='B.csv')
            preview_response = self.preview(f)
            upload_response = self.upload()

        self.assertDictEqual(
            preview_response.json(),
            dict(
                success=True,
                previewTable=[
                    dict(
                        name=self.img1.metadata.name,
                        link=reverse(
                            'annotation_tool',
                            kwargs=dict(image_id=self.img1.pk)),
                        createInfo="Will create 2 points, 2 annotations",
                        deleteInfo="Will delete 2 existing annotations",
                    ),
                    dict(
                        name=self.img2.metadata.name,
                        link=reverse(
                            'annotation_tool',
                            kwargs=dict(image_id=self.img2.pk)),
                        createInfo="Will create 2 points, 0 annotations",
                        deleteInfo="Will delete 1 existing annotations",
                    ),
                    dict(
                        name=self.img3.metadata.name,
                        link=reverse(
                            'annotation_tool',
                            kwargs=dict(image_id=self.img3.pk)),
                        createInfo="Will create 2 points, 2 annotations",
                    ),
                ],
                previewDetails=dict(
                    numImages=3,
                    totalPoints=6,
                    totalAnnotations=4,
                    numImagesWithExistingAnnotations=2,
                ),
            ),
        )

        self.assertDictEqual(upload_response.json(), dict(success=True))

        values_set = set(
            Point.objects.filter(
                image__in=[self.img1, self.img2, self.img3]) \
            .values_list('row', 'column', 'point_number', 'image_id'))
        self.assertSetEqual(values_set, {
            (10, 10, 1, self.img1.pk),
            (20, 20, 2, self.img1.pk),
            (30, 30, 1, self.img2.pk),
            (40, 40, 2, self.img2.pk),
            (50, 50, 1, self.img3.pk),
            (60, 60, 2, self.img3.pk),
        })

        annotations = Annotation.objects.filter(
            image__in=[self.img1, self.img2, self.img3])
        values_set = set(
            annotations.values_list('label__code', 'point_id', 'image_id'))
        self.assertSetEqual(values_set, {
            ('A', Point.objects.get(
                point_number=1, image=self.img1).pk, self.img1.pk),
            ('A', Point.objects.get(
                point_number=2, image=self.img1).pk, self.img1.pk),
            ('A', Point.objects.get(
                point_number=1, image=self.img3).pk, self.img3.pk),
            ('B', Point.objects.get(
                point_number=2, image=self.img3).pk, self.img3.pk),
        })

    def test_label_codes_different_case(self):
        """
        The CSV label codes can use different upper/lower case and still
        be matched to the corresponding labelset label codes.
        """
        self.client.force_login(self.user)

        # Make a longer-than-1-char label code so we can test that
        # lower() is being used on both the label's code and the CSV value
        labels = self.create_labels(self.user, self.source, ['Abc'], 'Group1')
        self.source.labelset.labels.add(labels[0])
        self.source.labelset.save()

        with BytesIO() as stream:
            writer = csv.writer(stream)
            writer.writerow(['Name', 'Row', 'Column', 'Label'])
            writer.writerow(['1.png', 40, 60, 'aBc'])

            f = ContentFile(stream.getvalue(), name='A.csv')
            preview_response = self.preview(f)
            upload_response = self.upload()

        self.assertDictEqual(
            preview_response.json(),
            dict(
                success=True,
                previewTable=[
                    dict(
                        name=self.img1.metadata.name,
                        link=reverse(
                            'annotation_tool',
                            kwargs=dict(image_id=self.img1.pk)),
                        createInfo="Will create 1 points, 1 annotations",
                    ),
                ],
                previewDetails=dict(
                    numImages=1,
                    totalPoints=1,
                    totalAnnotations=1,
                    numImagesWithExistingAnnotations=0,
                ),
            ),
        )

        self.assertDictEqual(upload_response.json(), dict(success=True))

        values_set = set(
            Point.objects.filter(image__in=[self.img1]) \
            .values_list('row', 'column', 'point_number', 'image_id'))
        self.assertSetEqual(values_set, {
            (40, 60, 1, self.img1.pk),
        })

        annotations = Annotation.objects.filter(image__in=[self.img1])
        values_set = set(
            annotations.values_list('label__code', 'point_id', 'image_id'))
        self.assertSetEqual(values_set, {
            ('Abc', Point.objects.get(
                point_number=1, image=self.img1).pk, self.img1.pk),
        })

    def test_skipped_filenames(self):
        """
        The CSV can have filenames that we don't recognize. Those rows
        will just be ignored.
        """
        self.client.force_login(self.user)

        with BytesIO() as stream:
            writer = csv.writer(stream)
            writer.writerow(['Name', 'Row', 'Column', 'Label'])
            writer.writerow(['1.png', 50, 50, 'A'])
            writer.writerow(['4.png', 40, 60, 'B'])

            f = ContentFile(stream.getvalue(), name='A.csv')
            preview_response = self.preview(f)
            upload_response = self.upload()

        self.assertDictEqual(
            preview_response.json(),
            dict(
                success=True,
                previewTable=[
                    dict(
                        name=self.img1.metadata.name,
                        link=reverse(
                            'annotation_tool',
                            kwargs=dict(image_id=self.img1.pk)),
                        createInfo="Will create 1 points, 1 annotations",
                    ),
                ],
                previewDetails=dict(
                    numImages=1,
                    totalPoints=1,
                    totalAnnotations=1,
                    numImagesWithExistingAnnotations=0,
                ),
            ),
        )

        self.assertDictEqual(upload_response.json(), dict(success=True))

        values_set = set(
            Point.objects.filter(image__in=[self.img1]) \
            .values_list('row', 'column', 'point_number', 'image_id'))
        self.assertSetEqual(values_set, {
            (50, 50, 1, self.img1.pk),
        })

        annotations = Annotation.objects.filter(image__in=[self.img1])
        values_set = set(
            annotations.values_list('label__code', 'point_id', 'image_id'))
        self.assertSetEqual(values_set, {
            ('A', Point.objects.get(
                point_number=1, image=self.img1).pk, self.img1.pk),
        })

    def test_skipped_csv_columns(self):
        """
        The CSV can have column names that we don't recognize. Those columns
        will just be ignored.
        """
        self.client.force_login(self.user)

        with BytesIO() as stream:
            writer = csv.writer(stream)
            writer.writerow(['Name', 'Row', 'Column', 'Annotator', 'Label'])
            writer.writerow(['1.png', 40, 60, 'Jane', 'A'])

            f = ContentFile(stream.getvalue(), name='A.csv')
            preview_response = self.preview(f)
            self.upload()

        self.assertDictEqual(
            preview_response.json(),
            dict(
                success=True,
                previewTable=[
                    dict(
                        name=self.img1.metadata.name,
                        link=reverse(
                            'annotation_tool',
                            kwargs=dict(image_id=self.img1.pk)),
                        createInfo="Will create 1 points, 1 annotations",
                    ),
                ],
                previewDetails=dict(
                    numImages=1,
                    totalPoints=1,
                    totalAnnotations=1,
                    numImagesWithExistingAnnotations=0,
                ),
            ),
        )

        values_set = set(
            Point.objects.filter(image__in=[self.img1]) \
            .values_list('row', 'column', 'point_number', 'image_id'))
        self.assertSetEqual(values_set, {
            (40, 60, 1, self.img1.pk),
        })

        annotations = Annotation.objects.filter(image__in=[self.img1])
        values_set = set(
            annotations.values_list('label__code', 'point_id', 'image_id'))
        self.assertSetEqual(values_set, {
            ('A', Point.objects.get(
                point_number=1, image=self.img1).pk, self.img1.pk),
        })

    def test_columns_different_order(self):
        """
        The CSV columns can be in a different order.
        """
        self.client.force_login(self.user)

        with BytesIO() as stream:
            writer = csv.writer(stream)
            writer.writerow(['Column', 'Name', 'Label', 'Row'])
            writer.writerow([60, '1.png', 'A', 40])

            f = ContentFile(stream.getvalue(), name='A.csv')
            preview_response = self.preview(f)
            self.upload()

        self.assertDictEqual(
            preview_response.json(),
            dict(
                success=True,
                previewTable=[
                    dict(
                        name=self.img1.metadata.name,
                        link=reverse(
                            'annotation_tool',
                            kwargs=dict(image_id=self.img1.pk)),
                        createInfo="Will create 1 points, 1 annotations",
                    ),
                ],
                previewDetails=dict(
                    numImages=1,
                    totalPoints=1,
                    totalAnnotations=1,
                    numImagesWithExistingAnnotations=0,
                ),
            ),
        )

        values_set = set(
            Point.objects.filter(image__in=[self.img1]) \
            .values_list('row', 'column', 'point_number', 'image_id'))
        self.assertSetEqual(values_set, {
            (40, 60, 1, self.img1.pk),
        })

        annotations = Annotation.objects.filter(image__in=[self.img1])
        values_set = set(
            annotations.values_list('label__code', 'point_id', 'image_id'))
        self.assertSetEqual(values_set, {
            ('A', Point.objects.get(
                point_number=1, image=self.img1).pk, self.img1.pk),
        })

    def test_columns_different_case(self):
        """
        The CSV column names can use different upper/lower case and still
        be matched to the expected column names.
        """
        self.client.force_login(self.user)

        with BytesIO() as stream:
            writer = csv.writer(stream)
            writer.writerow(['name', 'ROW', 'coLUmN', 'Label'])
            writer.writerow(['1.png', 40, 60, 'A'])

            f = ContentFile(stream.getvalue(), name='A.csv')
            preview_response = self.preview(f)
            upload_response = self.upload()

        self.assertDictEqual(
            preview_response.json(),
            dict(
                success=True,
                previewTable=[
                    dict(
                        name=self.img1.metadata.name,
                        link=reverse(
                            'annotation_tool',
                            kwargs=dict(image_id=self.img1.pk)),
                        createInfo="Will create 1 points, 1 annotations",
                    ),
                ],
                previewDetails=dict(
                    numImages=1,
                    totalPoints=1,
                    totalAnnotations=1,
                    numImagesWithExistingAnnotations=0,
                ),
            ),
        )

        self.assertDictEqual(upload_response.json(), dict(success=True))

        values_set = set(
            Point.objects.filter(image__in=[self.img1]) \
            .values_list('row', 'column', 'point_number', 'image_id'))
        self.assertSetEqual(values_set, {
            (40, 60, 1, self.img1.pk),
        })

        annotations = Annotation.objects.filter(image__in=[self.img1])
        values_set = set(
            annotations.values_list('label__code', 'point_id', 'image_id'))
        self.assertSetEqual(values_set, {
            ('A', Point.objects.get(
                point_number=1, image=self.img1).pk, self.img1.pk),
        })

    def test_surrounding_whitespace(self):
        """Strip whitespace surrounding the CSV values."""
        self.client.force_login(self.user)

        with BytesIO() as stream:
            writer = csv.writer(stream)
            writer.writerow(['Name ', '  Row', '\tColumn\t', '\tLabel    '])
            writer.writerow(['\t1.png', ' 40', '    60   ', 'A'])

            f = ContentFile(stream.getvalue(), name='A.csv')
            preview_response = self.preview(f)
            upload_response = self.upload()

        self.assertDictEqual(
            preview_response.json(),
            dict(
                success=True,
                previewTable=[
                    dict(
                        name=self.img1.metadata.name,
                        link=reverse(
                            'annotation_tool',
                            kwargs=dict(image_id=self.img1.pk)),
                        createInfo="Will create 1 points, 1 annotations",
                    ),
                ],
                previewDetails=dict(
                    numImages=1,
                    totalPoints=1,
                    totalAnnotations=1,
                    numImagesWithExistingAnnotations=0,
                ),
            ),
        )

        self.assertDictEqual(upload_response.json(), dict(success=True))

        values_set = set(
            Point.objects.filter(image__in=[self.img1]) \
            .values_list('row', 'column', 'point_number', 'image_id'))
        self.assertSetEqual(values_set, {
            (40, 60, 1, self.img1.pk),
        })

        annotations = Annotation.objects.filter(image__in=[self.img1])
        values_set = set(
            annotations.values_list('label__code', 'point_id', 'image_id'))
        self.assertSetEqual(values_set, {
            ('A', Point.objects.get(
                point_number=1, image=self.img1).pk, self.img1.pk),
        })


class UploadAnnotationsMultipleSourcesTest(ClientTest):
    """
    Test involving multiple sources.
    """
    @classmethod
    def setUpTestData(cls):
        super(UploadAnnotationsMultipleSourcesTest, cls).setUpTestData()

        cls.user = cls.create_user()
        cls.source = cls.create_source(cls.user)
        cls.source2 = cls.create_source(cls.user)

        labels = cls.create_labels(cls.user, cls.source, ['A', 'B'], 'Group1')
        cls.create_labelset(cls.user, cls.source, labels)
        cls.create_labelset(cls.user, cls.source2, labels)

        cls.img1_s1 = cls.upload_image_new(
            cls.user, cls.source,
            image_options=dict(filename='1.png', width=100, height=100))
        cls.img1_s2 = cls.upload_image_new(
            cls.user, cls.source2,
            image_options=dict(filename='1.png', width=100, height=100))
        cls.img2_s2 = cls.upload_image_new(
            cls.user, cls.source2,
            image_options=dict(filename='2.png', width=100, height=100))

    def preview1(self, csv_file):
        return self.client.post(
            reverse(
                'upload_annotations_preview_ajax',
                kwargs={'source_id': self.source.pk}),
            {'csv_file': csv_file},
        )

    def upload1(self):
        return self.client.post(
            reverse(
                'upload_annotations_ajax',
                kwargs={'source_id': self.source.pk}),
        )

    def preview2(self, csv_file):
        return self.client.post(
            reverse(
                'upload_annotations_preview_ajax',
                kwargs={'source_id': self.source2.pk}),
            {'csv_file': csv_file},
        )

    def upload2(self):
        return self.client.post(
            reverse(
                'upload_annotations_ajax',
                kwargs={'source_id': self.source2.pk}),
        )

    def test_other_sources_unaffected(self):
        """
        We shouldn't touch images of other sources which happen to have
        the same image names.
        """
        self.client.force_login(self.user)

        # Upload to source 2
        with BytesIO() as stream:
            writer = csv.writer(stream)
            writer.writerow(['Name', 'Row', 'Column', 'Label'])
            writer.writerow(['1.png', 10, 10, 'B'])
            writer.writerow(['1.png', 20, 20, 'B'])
            writer.writerow(['2.png', 15, 15, 'A'])
            writer.writerow(['2.png', 25, 25, 'A'])

            f = ContentFile(stream.getvalue(), name='A.csv')
            self.preview2(f)
            self.upload2()

        # Upload to source 1
        with BytesIO() as stream:
            writer = csv.writer(stream)
            writer.writerow(['Name', 'Row', 'Column', 'Label'])
            writer.writerow(['1.png', 50, 50, 'A'])
            writer.writerow(['2.png', 40, 60, 'B'])

            f = ContentFile(stream.getvalue(), name='B.csv')
            preview_response = self.preview1(f)
            upload_response = self.upload1()

        # Check source 1 responses

        self.assertDictEqual(
            preview_response.json(),
            dict(
                success=True,
                previewTable=[
                    dict(
                        name=self.img1_s1.metadata.name,
                        link=reverse(
                            'annotation_tool',
                            kwargs=dict(image_id=self.img1_s1.pk)),
                        createInfo="Will create 1 points, 1 annotations",
                    ),
                ],
                previewDetails=dict(
                    numImages=1,
                    totalPoints=1,
                    totalAnnotations=1,
                    numImagesWithExistingAnnotations=0,
                ),
            ),
        )

        self.assertDictEqual(upload_response.json(), dict(success=True))

        # Check source 1 objects

        values_set = set(
            Point.objects.filter(image__in=[self.img1_s1]) \
            .values_list('row', 'column', 'point_number', 'image_id'))
        self.assertSetEqual(values_set, {
            (50, 50, 1, self.img1_s1.pk),
        })

        annotations = Annotation.objects.filter(image__in=[self.img1_s1])
        values_set = set(
            annotations.values_list('label__code', 'point_id', 'image_id'))
        self.assertSetEqual(values_set, {
            ('A', Point.objects.get(
                point_number=1, image=self.img1_s1).pk, self.img1_s1.pk),
        })

        # Check source 2 objects

        values_set = set(
            Point.objects.filter(image__in=[self.img1_s2, self.img2_s2]) \
            .values_list('row', 'column', 'point_number', 'image_id'))
        self.assertSetEqual(values_set, {
            (10, 10, 1, self.img1_s2.pk),
            (20, 20, 2, self.img1_s2.pk),
            (15, 15, 1, self.img2_s2.pk),
            (25, 25, 2, self.img2_s2.pk),
        })

        annotations = Annotation.objects.filter(
            image__in=[self.img1_s2, self.img2_s2])
        values_set = set(
            annotations.values_list('label__code', 'point_id', 'image_id'))
        self.assertSetEqual(values_set, {
            ('B', Point.objects.get(
                point_number=1, image=self.img1_s2).pk, self.img1_s2.pk),
            ('B', Point.objects.get(
                point_number=2, image=self.img1_s2).pk, self.img1_s2.pk),
            ('A', Point.objects.get(
                point_number=1, image=self.img2_s2).pk, self.img2_s2.pk),
            ('A', Point.objects.get(
                point_number=2, image=self.img2_s2).pk, self.img2_s2.pk),
        })


class UploadAnnotationsPreviewErrorTest(ClientTest):
    """
    Upload preview, error cases (mainly related to CSV content).
    """
    @classmethod
    def setUpTestData(cls):
        super(UploadAnnotationsPreviewErrorTest, cls).setUpTestData()

        cls.user = cls.create_user()
        cls.source = cls.create_source(cls.user)
        # Labels in labelset
        labels = cls.create_labels(cls.user, cls.source, ['A', 'B'], 'Group1')
        cls.create_labelset(cls.user, cls.source, labels)
        # Label not in labelset
        cls.create_labels(cls.user, cls.source, ['C'], 'Group1')

        cls.img1 = cls.upload_image_new(
            cls.user, cls.source,
            image_options=dict(filename='1.png', width=100, height=200))
        cls.img2 = cls.upload_image_new(
            cls.user, cls.source,
            image_options=dict(filename='2.png', width=200, height=100))

    def preview(self, csv_file):
        return self.client.post(
            reverse(
                'upload_annotations_preview_ajax',
                kwargs={'source_id': self.source.pk}),
            {'csv_file': csv_file},
        )

    def test_no_name_column(self):
        """
        No CSV columns correspond to the name field.
        """
        self.client.force_login(self.user)

        with BytesIO() as stream:
            writer = csv.writer(stream)
            writer.writerow(['Row', 'Column', 'Label'])
            writer.writerow([50, 50, 'A'])
            writer.writerow([40, 60, 'B'])

            f = ContentFile(stream.getvalue(), name='A.csv')
            preview_response = self.preview(f)

        self.assertDictEqual(
            preview_response.json(),
            dict(error="CSV must have a column called Name"),
        )

    def test_no_row_column(self):
        """
        No CSV columns correspond to the row field.
        """
        self.client.force_login(self.user)

        with BytesIO() as stream:
            writer = csv.writer(stream)
            writer.writerow(['Name', 'Column', 'Label'])
            writer.writerow(['1.png', 50, 'A'])
            writer.writerow(['1.png', 60, 'B'])

            f = ContentFile(stream.getvalue(), name='A.csv')
            preview_response = self.preview(f)

        self.assertDictEqual(
            preview_response.json(),
            dict(error="CSV must have a column called Row"),
        )

    def test_no_column_column(self):
        """
        No CSV columns correspond to the column field.
        """
        self.client.force_login(self.user)

        with BytesIO() as stream:
            writer = csv.writer(stream)
            writer.writerow(['Name', 'Row'])
            writer.writerow(['1.png', 50])
            writer.writerow(['1.png', 40])

            f = ContentFile(stream.getvalue(), name='A.csv')
            preview_response = self.preview(f)

        self.assertDictEqual(
            preview_response.json(),
            dict(error="CSV must have a column called Column"),
        )

    def test_missing_row(self):
        """
        A row is missing the row field.
        """
        self.client.force_login(self.user)

        with BytesIO() as stream:
            writer = csv.writer(stream)
            writer.writerow(['Name', 'Row', 'Column'])
            writer.writerow(['1.png', 50, 50])
            writer.writerow(['1.png', '', 60])

            f = ContentFile(stream.getvalue(), name='A.csv')
            preview_response = self.preview(f)

        self.assertDictEqual(
            preview_response.json(),
            dict(error="CSV row 3 is missing a Row value"),
        )

    def test_missing_column(self):
        """
        A row is missing the column field.
        """
        self.client.force_login(self.user)

        with BytesIO() as stream:
            writer = csv.writer(stream)
            writer.writerow(['Name', 'Row', 'Column'])
            writer.writerow(['1.png', 50, ''])
            writer.writerow(['1.png', 40, 60])

            f = ContentFile(stream.getvalue(), name='A.csv')
            preview_response = self.preview(f)

        self.assertDictEqual(
            preview_response.json(),
            dict(error="CSV row 2 is missing a Column value"),
        )

    def test_row_not_positive_integer(self):
        self.client.force_login(self.user)

        with BytesIO() as stream:
            writer = csv.writer(stream)
            writer.writerow(['Name', 'Row', 'Column'])
            writer.writerow(['1.png', 'abc', 50])

            f = ContentFile(stream.getvalue(), name='A.csv')
            preview_response = self.preview(f)

        self.assertDictEqual(
            preview_response.json(),
            dict(error="Row value is not a positive integer: abc"),
        )

    def test_column_not_positive_integer(self):
        """
        A row is missing the column field.
        """
        self.client.force_login(self.user)

        with BytesIO() as stream:
            writer = csv.writer(stream)
            writer.writerow(['Name', 'Row', 'Column'])
            writer.writerow(['1.png', 50, 0])

            f = ContentFile(stream.getvalue(), name='A.csv')
            preview_response = self.preview(f)

        self.assertDictEqual(
            preview_response.json(),
            dict(error="Column value is not a positive integer: 0"),
        )

    def test_row_too_large(self):
        self.client.force_login(self.user)

        with BytesIO() as stream:
            writer = csv.writer(stream)
            writer.writerow(['Name', 'Row', 'Column'])
            writer.writerow(['2.png', 101, 50])

            f = ContentFile(stream.getvalue(), name='A.csv')
            preview_response = self.preview(f)

        self.assertDictEqual(
            preview_response.json(),
            dict(error=(
                "Row value of 101 is too large for image 2.png,"
                " which has dimensions 200 x 100")),
        )

    def test_column_too_large(self):
        self.client.force_login(self.user)

        with BytesIO() as stream:
            writer = csv.writer(stream)
            writer.writerow(['Name', 'Row', 'Column'])
            writer.writerow(['1.png', 150, 101])

            f = ContentFile(stream.getvalue(), name='A.csv')
            preview_response = self.preview(f)

        self.assertDictEqual(
            preview_response.json(),
            dict(error=(
                "Column value of 101 is too large for image 1.png,"
                " which has dimensions 100 x 200")),
        )

    def test_multiple_points_same_row_column(self):
        """
        More than one point in the same image on the exact same position
        (same row and same column) should not be allowed.
        """
        self.client.force_login(self.user)

        with BytesIO() as stream:
            writer = csv.writer(stream)
            writer.writerow(['Name', 'Row', 'Column', 'Label'])
            writer.writerow(['1.png', 150, 90, 'A'])
            writer.writerow(['1.png', 150, 90, 'B'])

            f = ContentFile(stream.getvalue(), name='A.csv')
            preview_response = self.preview(f)

        self.assertDictEqual(
            preview_response.json(),
            dict(error=(
                "Image 1.png has multiple points on the same position:"
                " row 150, column 90")),
        )

    def test_label_not_in_labelset(self):
        self.client.force_login(self.user)

        with BytesIO() as stream:
            writer = csv.writer(stream)
            writer.writerow(['Name', 'Row', 'Column', 'Label'])
            writer.writerow(['1.png', 50, 50, 'C'])

            f = ContentFile(stream.getvalue(), name='A.csv')
            preview_response = self.preview(f)

        self.assertDictEqual(
            preview_response.json(),
            dict(error="No label of code C found in this source's labelset"),
        )

    def test_label_not_in_site(self):
        """
        Label doesn't exist in the entire site.
        Should just get the same message as 'not in labelset'.
        """
        self.client.force_login(self.user)

        with BytesIO() as stream:
            writer = csv.writer(stream)
            writer.writerow(['Name', 'Row', 'Column', 'Label'])
            writer.writerow(['1.png', 50, 50, 'D'])

            f = ContentFile(stream.getvalue(), name='A.csv')
            preview_response = self.preview(f)

        self.assertDictEqual(
            preview_response.json(),
            dict(error="No label of code D found in this source's labelset"),
        )

    def test_no_specified_images_found_in_source(self):
        """
        No CSV rows have a filename that can be found in the source.
        """
        self.client.force_login(self.user)

        with BytesIO() as stream:
            writer = csv.writer(stream)
            writer.writerow(['Name', 'Row', 'Column'])
            writer.writerow(['3.png', 50, 50])
            writer.writerow(['4.png', 40, 60])

            f = ContentFile(stream.getvalue(), name='A.csv')
            preview_response = self.preview(f)

        self.assertDictEqual(
            preview_response.json(),
            dict(
                error="No matching filenames found in the source",
            ),
        )


class UploadAnnotationsNoLabelsetTest(ClientTest):
    """
    Point/annotation upload attempts with no labelset.
    """
    @classmethod
    def setUpTestData(cls):
        super(UploadAnnotationsNoLabelsetTest, cls).setUpTestData()

        cls.user = cls.create_user()
        cls.source = cls.create_source(cls.user)

        cls.img1 = cls.upload_image_new(
            cls.user, cls.source,
            image_options=dict(filename='1.png', width=100, height=100))

    def preview(self, csv_file):
        return self.client.post(
            reverse(
                'upload_annotations_preview_ajax',
                kwargs={'source_id': self.source.pk}),
            {'csv_file': csv_file},
        )

    def upload(self):
        return self.client.post(
            reverse(
                'upload_annotations_ajax',
                kwargs={'source_id': self.source.pk}),
        )

    def test_points_only(self):
        """
        No annotations on specified points. Should work.
        """
        self.client.force_login(self.user)

        with BytesIO() as stream:
            writer = csv.writer(stream)
            writer.writerow(['Name', 'Row', 'Column'])
            writer.writerow(['1.png', 50, 50])
            writer.writerow(['1.png', 40, 60])
            writer.writerow(['1.png', 30, 70])

            f = ContentFile(stream.getvalue(), name='A.csv')
            preview_response = self.preview(f)
            upload_response = self.upload()

        self.assertDictEqual(
            preview_response.json(),
            dict(
                success=True,
                previewTable=[
                    dict(
                        name=self.img1.metadata.name,
                        link=reverse(
                            'annotation_tool',
                            kwargs=dict(image_id=self.img1.pk)),
                        createInfo="Will create 3 points, 0 annotations",
                    ),
                ],
                previewDetails=dict(
                    numImages=1,
                    totalPoints=3,
                    totalAnnotations=0,
                    numImagesWithExistingAnnotations=0,
                ),
            ),
        )

        self.assertDictEqual(upload_response.json(), dict(success=True))

        values_set = set(
            Point.objects.filter(image__in=[self.img1]) \
            .values_list('row', 'column', 'point_number', 'image_id'))
        self.assertSetEqual(values_set, {
            (50, 50, 1, self.img1.pk),
            (40, 60, 2, self.img1.pk),
            (30, 70, 3, self.img1.pk),
        })

    def test_with_annotations(self):
        """
        With annotations. Should fail at the preview.
        """
        self.client.force_login(self.user)

        with BytesIO() as stream:
            writer = csv.writer(stream)
            writer.writerow(['Name', 'Row', 'Column', 'Label'])
            writer.writerow(['1.png', 50, 50, 'A'])
            writer.writerow(['1.png', 40, 60, 'B'])
            writer.writerow(['2.png', 30, 70, 'A'])
            writer.writerow(['2.png', 20, 80, 'A'])

            f = ContentFile(stream.getvalue(), name='A.csv')
            preview_response = self.preview(f)

        self.assertDictEqual(
            preview_response.json(),
            dict(
                error="No label of code A found in this source's labelset",
            ),
        )
