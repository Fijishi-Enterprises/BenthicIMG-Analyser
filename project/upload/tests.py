import csv
from collections import defaultdict
import datetime
from io import BytesIO
import os
import re
import tempfile

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.urlresolvers import reverse
from django.utils import timezone
from annotations.model_utils import AnnotationAreaUtils
from annotations.models import Annotation
from images.model_utils import PointGen
from images.models import Source, Image, Point
from lib import str_consts
from lib.test_utils import ClientTest, sample_image_as_file, create_sample_image


class ImageUploadBaseTest(ClientTest):
    """
    Base test class for the image upload page.

    This is an abstract class of sorts, as it doesn't actually contain
    any test methods.  However, its subclasses have test methods.
    """
    fixtures = ['test_users.yaml', 'test_sources_with_different_keys.yaml']
    source_member_roles = [
        ('0 keys', 'user2', Source.PermTypes.ADMIN.code),
        ('1 key', 'user2', Source.PermTypes.ADMIN.code),
        ('2 keys', 'user2', Source.PermTypes.ADMIN.code),
        ('5 keys', 'user2', Source.PermTypes.ADMIN.code),
    ]

    def setUp(self):
        super(ImageUploadBaseTest, self).setUp()

        # Default user; individual tests are free to change it
        self.client.login(username='user2', password='secret')

        # Default source; individual tests are free to change it
        self.source_id = Source.objects.get(name='1 key').pk

    def get_source_image_count(self):
        return Image.objects.filter(source=Source.objects.get(pk=self.source_id)).count()

    def get_full_upload_options(self, specified_options):
        full_options = dict(self.default_upload_params)
        full_options.update(specified_options)
        return full_options

    def upload_image_test(self, filename,
                          expecting_dupe=False,
                          expected_error=None,
                          **options):
        """
        Upload a single image via the Ajax view, and perform a few checks
        to see that the upload worked.

        (Multi-image upload only takes place on the client side; it's really
        just a series of single-image uploads on the server side. So unit
        testing multi-image upload doesn't make sense unless we can
        test on the client side, with Selenium or something.)

        :param filename: The image file's filepath as a string, relative to
            <settings.SAMPLE_UPLOADABLES_ROOT>/data.
        :param expecting_dupe: True if we expect the image to be a duplicate
            of an existing image, False otherwise.
        :param expected_error: Expected error message, if any.
        :param options: Extra options to include in the Ajax-image-upload
            request.
        :return: Tuple of (new image id, response from Ajax-image-upload).
            This way, the calling function can do some additional checks
            if it wants to.
        """
        old_source_image_count = self.get_source_image_count()

        image_id, response = self.upload_image(filename, **options)
        response_json = response.json()

        new_source_image_count = self.get_source_image_count()

        if expected_error:

            self.assertEqual(response_json['status'], 'error')
            self.assertEqual(response_json['message'], expected_error)

            if settings.UNIT_TEST_VERBOSITY >= 1:
                print "Error message:\n{error}".format(error=response_json['message'])

            # Error, so nothing was uploaded.
            # The number of images in the source should have stayed the same.
            self.assertEqual(new_source_image_count, old_source_image_count)

        else:

            if expecting_dupe:
                # We just replaced a duplicate image.
                full_options = self.get_full_upload_options(options)

                if full_options['skip_or_upload_duplicates'] == 'skip':
                    self.assertEqual(response_json['status'], 'error')
                else:  # replace
                    self.assertEqual(response_json['status'], 'ok')

                # The number of images in the source should have stayed the same.
                self.assertEqual(new_source_image_count, old_source_image_count)
            else:
                # We uploaded a new, non-duplicate image.
                self.assertEqual(response_json['status'], 'ok')

                # The number of images in the source should have gone up by 1.
                self.assertEqual(new_source_image_count, 1+old_source_image_count)

        return image_id, response

    def check_fields_for_non_annotation_upload(self, img):

        # Uploading without points/annotations.
        self.assertFalse(img.status.annotatedByHuman)
        self.assertEqual(img.point_generation_method, img.source.default_point_generation_method)
        self.assertEqual(img.metadata.annotation_area, img.source.image_annotation_area)

    def upload_image_test_with_field_checks(self, filename,
                                            expecting_dupe=False,
                                            expected_error=None,
                                            **options):
        """
        Like upload_image_test(), but with additional checks that the
        various image fields are set correctly.
        """
        datetime_before_upload = timezone.now()

        image_id, response = self.upload_image_test(
            filename,
            expecting_dupe,
            expected_error,
            **options
        )

        img = Image.objects.get(pk=image_id)

        # Not sure if we can check the file location in a cross-platform way,
        # so we'll skip a check of original_file.path for now.
        if settings.UNIT_TEST_VERBOSITY >= 1:
            print "Uploaded file's path: {path}".format(path=img.original_file.path)

        self.assertEqual(img.original_height, 400)
        self.assertEqual(img.original_width, 400)

        self.assertTrue(datetime_before_upload <= img.upload_date)
        self.assertTrue(img.upload_date <= timezone.now())

        # Check that the user who uploaded the image is the
        # currently logged in user.
        self.assertEqual(
            img.uploaded_by.id, int(self.client.session['_auth_user_id']))

        # Status fields.
        self.assertFalse(img.status.preprocessed)
        self.assertTrue(img.status.hasRandomPoints)
        self.assertFalse(img.status.featuresExtracted)
        self.assertFalse(img.status.annotatedByRobot)
        self.assertFalse(img.status.featureFileHasHumanLabels)
        self.assertFalse(img.status.usedInCurrentModel)

        # cm height.
        self.assertEqual(img.metadata.height_in_cm, img.source.image_height_in_cm)

        full_options = self.get_full_upload_options(options)

        if full_options['is_uploading_points_or_annotations'] == True:

            # Uploading with points/annotations.

            # Pointgen method and annotation area should both indicate that
            # points have been imported.
            self.assertEqual(
                PointGen.db_to_args_format(img.point_generation_method)['point_generation_type'],
                PointGen.Types.IMPORTED,
            )
            self.assertEqual(
                img.metadata.annotation_area,
                AnnotationAreaUtils.IMPORTED_STR,
            )

            # Depending on whether we're uploading annotations, the
            # annotatedByHuman status flag may or may not apply.
            if full_options['is_uploading_annotations_not_just_points'] == 'yes':
                # Points + annotations upload.
                self.assertTrue(img.status.annotatedByHuman)

            else:  # 'no'
                # Points only upload.
                self.assertFalse(img.status.annotatedByHuman)

        else:  # False

            self.check_fields_for_non_annotation_upload(img)

        # Other metadata fields aren't covered here because:
        # - name, photo_date, aux1/2/3/4/5: covered by filename tests
        # - latitude, longitude, depth, camera, photographer, water_quality,
        #   strobes, framing, balance, comments: not specifiable from the
        #   upload page

        return image_id, response


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
            {'filenames[]': ['3.png']},
        )

        response_json = response.json()
        self.assertDictEqual(
            response_json,
            dict(
                statusList=[dict(
                    status='ok',
                )]
            ),
        )

    def test_detect_dupe(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse(
                'image_upload_preview_ajax',
                kwargs={'source_id': self.source.pk}),
            {'filenames[]': ['1.png']},
        )

        response_json = response.json()
        self.assertDictEqual(
            response_json,
            dict(
                statusList=[dict(
                    status='dupe',
                    url=reverse('image_detail', args=[self.img1.id]),
                    title=self.img1.get_image_element_title(),
                )]
            ),
        )

    def test_detect_multiple_dupes(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse(
                'image_upload_preview_ajax',
                kwargs={'source_id': self.source.pk}),
            {'filenames[]': ['1.png', '2.png', '3.png']},
        )

        response_json = response.json()
        self.assertDictEqual(
            response_json,
            dict(
                statusList=[
                    dict(
                        status='dupe',
                        url=reverse('image_detail', args=[self.img1.id]),
                        title=self.img1.get_image_element_title(),
                    ),
                    dict(
                        status='dupe',
                        url=reverse('image_detail', args=[self.img2.id]),
                        title=self.img2.get_image_element_title(),
                    ),
                    dict(
                        status='ok',
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
        self.assertEqual(response_json['status'], 'ok')
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
        self.assertEqual(response_json['status'], 'ok')
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


class UploadInvalidImageTest(ClientTest):
    """
    Image upload tests: errors related to the image files, such as errors
    about non-images.
    """
    @classmethod
    def setUpTestData(cls):
        super(UploadInvalidImageTest, cls).setUpTestData()

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
            dict(
                status='error',
                message=(
                    "The file is either a corrupt image,"
                    " or in a file format that we don't support."
                ),
                link=None,
                title=None,
            )
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
            dict(
                status='error',
                message="This image file format isn't supported.",
                link=None,
                title=None,
            )
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
            dict(
                status='error',
                message="The submitted file is empty.",
                link=None,
                title=None,
            )
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
            dict(
                status='error',
                message="Ensure the image dimensions are at most 599 x 1000.",
                link=None,
                title=None,
            )
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
            dict(
                status='error',
                message="Ensure the image dimensions are at most 1000 x 449.",
                link=None,
                title=None,
            )
        )

    # TODO: Test an upload larger than the upload limit
    # TODO: Test an upload larger than FILE_UPLOAD_MAX_MEMORY_SIZE, but
    # smaller than the upload limit (should NOT get an error)
    #
    # Not sure how to craft an image of a specific size though. Maybe there
    # is some metadata field that can be arbitrarily long?
    # Also, testing the upload limit should be done on the client side,
    # before the image is actually uploaded.
    # So might have to be a client-side test.


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

    def upload(self, csv_file):
        return self.client.post(
            reverse(
                'upload_metadata_ajax',
                kwargs={'source_id': self.source.pk}),
            {'csv_file': csv_file},
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
            f = ContentFile(stream.getvalue(), name='A.csv')
            upload_response = self.upload(f)

        self.assertDictEqual(
            preview_response.json(),
            dict(
                success=True,
                metadataPreviewTable=[
                    self.standard_column_order,
                    ['1.png', '2016-07-18', 'SiteA', 'Fringing Reef', '2-4',
                     'Q5', '28', '50', '20.18', '-59.64', '30m',
                     'Canon', 'Bob Doe', 'Mostly clear', '2x blue', 'FG-16',
                     'WB-03', 'A bit off to the left from the transect line.'],
                    ['2.png', '', 'SiteB', '10m out', '', '', '', '50',
                     '', '', '', 'Canon', '', '', '', 'FG-15', '', ''],
                ],
                numImages=2,
                numFieldsReplaced=0,
            ),
        )

        self.assertDictEqual(upload_response.json(), dict(success=True))

        meta1 = self.img1.metadata
        meta1.refresh_from_db()
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

        meta2 = self.img2.metadata
        meta2.refresh_from_db()
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
            f = ContentFile(stream.getvalue(), name='A.csv')
            upload_response = self.upload(f)

        self.assertDictEqual(
            preview_response.json(),
            dict(
                success=True,
                metadataPreviewTable=[
                    self.standard_column_order,
                    ['1.png', '2016-07-18', 'SiteA',
                     'Fringing Reef', '2-4',
                     'Q5', '28', '50', '20.18', '-59.64', '30m',
                     'Canon', '', '', '', '', '', ''],
                ],
                numImages=1,
                numFieldsReplaced=0,
            ),
        )

        self.assertDictEqual(upload_response.json(), dict(success=True))

        meta1.refresh_from_db()
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
            f = ContentFile(stream.getvalue(), name='A.csv')
            upload_response = self.upload(f)

        self.assertDictEqual(
            preview_response.json(),
            dict(
                success=True,
                metadataPreviewTable=[
                    self.standard_column_order,
                    ['1.png', ['2016-07-18', '2014-02-27'], ['SiteA', 'SiteC'],
                     'Fringing Reef', '2-4',
                     'Q5', '28', ['', '50'], '20.18', '-59.64', '30m',
                     ['', 'Nikon'], '', '', '', '', '', ''],
                ],
                numImages=1,
                numFieldsReplaced=4,
            ),
        )

        self.assertDictEqual(upload_response.json(), dict(success=True))

        meta1.refresh_from_db()
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
            f = ContentFile(stream.getvalue(), name='A.csv')
            upload_response = self.upload(f)

        self.assertDictEqual(
            preview_response.json(),
            dict(
                success=True,
                metadataPreviewTable=[
                    column_names,
                    ['1.png', ['SiteA', 'SiteC'],
                     'Fringing Reef', '2-4'],
                ],
                numImages=1,
                numFieldsReplaced=1,
            ),
        )

        self.assertDictEqual(upload_response.json(), dict(success=True))

        meta1.refresh_from_db()
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
            f = ContentFile(stream.getvalue(), name='A.csv')
            upload_response = self.upload(f)

        self.assertDictEqual(
            preview_response.json(),
            dict(
                success=True,
                metadataPreviewTable=[
                    ['Name', 'Site', 'Habitat', 'Transect'],
                    ['1.png', 'SiteA', 'Fringing Reef', '2-4'],
                ],
                numImages=1,
                numFieldsReplaced=0,
            ),
        )

        self.assertDictEqual(upload_response.json(), dict(success=True))

        meta1 = self.img1.metadata
        meta1.refresh_from_db()
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
            f = ContentFile(stream.getvalue(), name='A.csv')
            upload_response = self.upload(f)

        self.assertDictEqual(
            preview_response.json(),
            dict(
                success=True,
                metadataPreviewTable=[
                    ['Name', 'Site'],
                    ['1.png', 'SiteA'],
                ],
                numImages=1,
                numFieldsReplaced=0,
            ),
        )

        self.assertDictEqual(upload_response.json(), dict(success=True))

        meta1 = self.img1.metadata
        meta1.refresh_from_db()
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
            f = ContentFile(stream.getvalue(), name='A.csv')
            upload_response = self.upload(f)

        self.assertDictEqual(
            preview_response.json(),
            dict(
                success=True,
                metadataPreviewTable=[
                    column_names,
                    ['2-4', 'SiteA', '1.png'],
                ],
                numImages=1,
                numFieldsReplaced=0,
            ),
        )

        self.assertDictEqual(upload_response.json(), dict(success=True))

        meta1 = self.img1.metadata
        meta1.refresh_from_db()
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
            f = ContentFile(stream.getvalue(), name='A.csv')
            upload_response = self.upload(f)

        self.assertDictEqual(
            preview_response.json(),
            dict(
                success=True,
                metadataPreviewTable=[
                    ['Transect', 'Site', 'Name'],
                    ['2-4', 'SiteA', '1.png'],
                ],
                numImages=1,
                numFieldsReplaced=0,
            ),
        )

        self.assertDictEqual(upload_response.json(), dict(success=True))

        meta1 = self.img1.metadata
        meta1.refresh_from_db()
        self.assertEqual(meta1.name, '1.png')
        self.assertEqual(meta1.aux1, 'SiteA')
        self.assertEqual(meta1.aux3, '2-4')


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

    def test_dupe_column_names(self):
        """
        Two CSV columns have the same name.
        """
        self.client.force_login(self.user)

        column_names = ['Name', 'Latitude', 'LATITUDE']

        with BytesIO() as stream:
            writer = csv.DictWriter(stream, column_names)
            writer.writeheader()
            writer.writerow({
                'Name': '1.png',
                'Latitude': '24.08',
                'LATITUDE': '24.08',
            })

            f = ContentFile(stream.getvalue(), name='A.csv')
            preview_response = self.preview(f)

        self.assertDictEqual(
            preview_response.json(),
            dict(
                error=(
                    "Column name appears more than once: latitude"
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
                    "No 'Name' column found in CSV"
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
            dict(
                error=(
                    "No metadata columns other than 'Name' found in CSV"
                ),
            ),
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
                metadataPreviewTable=[
                    ['Name', 'Aux1'],
                    ['1.png', 'SiteA'],
                ],
                numImages=1,
                numFieldsReplaced=0,
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
                metadataPreviewTable=[
                    ['Name', 'Aux1'],
                    ['1.png', '\xe5\x9c\xb0\xe7\x82\xb9A'],
                ],
                numImages=1,
                numFieldsReplaced=0,
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
                metadataPreviewTable=[
                    ['Name', 'Aux1'],
                    ['1.png', 'SiteA'],
                ],
                numImages=1,
                numFieldsReplaced=0,
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
                metadataPreviewTable=[
                    ['Name', 'Aux1'],
                    ['1.png', 'SiteA,IsleB'],
                ],
                numImages=1,
                numFieldsReplaced=0,
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


class AnnotationUploadBaseTest(ImageUploadBaseTest):

    default_options = dict(
        is_uploading_points_or_annotations=True,
        is_uploading_annotations_not_just_points='yes',
    )

    def process_annotation_text(self, annotations_text, **extra_options):

        tmp_file = tempfile.NamedTemporaryFile(mode='w+t', suffix='.txt', delete=False)
        tmp_file.write(annotations_text)
        name = tmp_file.name
        tmp_file.close()
        tmp_file = open(name, 'rb')

        return self.process_open_annotation_file(tmp_file, **extra_options)

    def process_annotation_file(self, annotations_filename, **extra_options):

        annotations_file_dir = os.path.join(settings.SAMPLE_UPLOADABLES_ROOT, 'annotations_txt')
        annotations_filepath = os.path.join(annotations_file_dir, annotations_filename)
        annotations_file = open(annotations_filepath, 'rb')

        return self.process_open_annotation_file(annotations_file, **extra_options)

    def process_open_annotation_file(self, annotations_file, **extra_options):

        options = dict(self.default_options)
        options.update(extra_options)
        options.update(annotations_file=annotations_file)
        options.update(metadataOption='filenames')

        response = self.client.post(
            reverse('annotation_file_process_ajax', kwargs={'source_id': self.source_id}),
            options,
        )
        annotations_file.close()

        self.assertStatusOK(response)
        response_json = response.json()

        return response_json

    def process_annotations_and_upload(self, annotations_text, image_filenames,
                                       expected_annotations_per_image,
                                       expected_annotations, **extra_options):

        options = dict(self.default_options)
        options.update(extra_options)

        # Perform the annotation file check.
        response_content = self.process_annotation_text(annotations_text, **options)

        self.assertEqual(response_content['status'], 'ok')

        annotations_per_image = response_content['annotations_per_image']

        # Check annotations_per_image for correctness:
        # Check keys.
        self.assertEqual(
            set(annotations_per_image.keys()),
            set(expected_annotations_per_image.keys()),
        )
        # Check values.
        self.assertEqual(annotations_per_image, expected_annotations_per_image)

        # Modify options so we can pass it into the image-upload view.
        options['annotation_dict_id'] = response_content['annotation_dict_id']

        actual_annotations = defaultdict(set)

        for image_filename in image_filenames:

            # Upload the file, and test that the upload succeeds and that
            # image fields are set correctly.
            image_id, response = self.upload_image_test_with_field_checks(
                image_filename,
                **options
            )

            img = Image.objects.get(pk=image_id)
            img_title = img.get_image_element_title()

            # Test that points/annotations were generated correctly.
            pts = Point.objects.filter(image=img)

            for pt in pts:
                if options['is_uploading_annotations_not_just_points'] == 'yes':
                    anno = Annotation.objects.get(point=pt)
                    actual_annotations[img_title].add( (pt.row, pt.column, anno.label.code) )
                else:  # 'no'
                    actual_annotations[img_title].add( (pt.row, pt.column))


        # All images we specified should have annotations, and there
        # shouldn't be any annotations for images we didn't specify.
        self.assertEqual(set(actual_annotations.keys()), set(expected_annotations.keys()))

        # All the annotations we specified should be there.
        for img_key in expected_annotations:
            self.assertEqual(actual_annotations[img_key], expected_annotations[img_key])


class AnnotationUploadTest(AnnotationUploadBaseTest):

    fixtures = ['test_users.yaml', 'test_labels.yaml',
                'test_labelsets.yaml', 'test_sources_with_labelsets.yaml']
    source_member_roles = [
        ('Labelset 2keys', 'user2', Source.PermTypes.ADMIN.code),
    ]

    def setUp(self):
        ClientTest.setUp(self)
        self.client.login(username='user2', password='secret')
        self.source_id = Source.objects.get(name='Labelset 2keys').pk

        # Files to upload.
        self.image_filenames = [
            os.path.join('2keys', 'cool_001_2011-05-28.png'),
            os.path.join('2keys', 'cool_001_2012-05-28.png'),
            os.path.join('2keys', 'cool_002_2011-05-28.png'),
        ]

        self.annotation_file_contents_with_labels = (
            "cool; 001; 2011; 200; 300; Scarlet\n"
            "cool; 001; 2011; 50; 250; Lime\n"
            "cool; 001; 2011; 10; 10; Turq\n"
            "\n"
            "cool; 001; 2012; 1; 1; UMarine\n"
            "cool; 001; 2012; 400; 400; Lime\n"
            "\n"
            "cool; 002; 2011; 160; 40; Turq\n"
            "\n"
            "will_not_be_uploaded; 025; 2004; 1465; 797; UMarine\n"
        )
        self.annotation_file_contents_without_labels = (
            "cool; 001; 2011; 200; 300\n"
            "cool; 001; 2011; 50; 250\n"
            "cool; 001; 2011; 10; 10\n"
            "\n"
            "cool; 001; 2012; 1; 1\n"
            "cool; 001; 2012; 400; 400\n"
            "\n"
            "cool; 002; 2011; 160; 40\n"
            "\n"
            "will_not_be_uploaded; 025; 2004; 1465; 797\n"
        )

        # Number of annotations that should be recognized by the annotation
        # file check.  Note that the annotation file check does not know
        # what image files are actually going to be uploaded; so if the
        # annotation file contains annotations for image A, then it would
        # report an annotation count for image A even if A isn't uploaded.
        self.expected_annotations_per_image = {
            'cool;001;2011': 3,
            'cool;001;2012': 2,
            'cool;002;2011': 1,
            'will_not_be_uploaded;025;2004': 1,
        }

        # The annotations that should actually be created after the upload
        # completes.
        self.expected_annotations = {
            'cool_001_2011-05-28.png': set([
                (200, 300, 'Scarlet'),
                (50, 250, 'Lime'),
                (10, 10, 'Turq'),
            ]),
            'cool_001_2012-05-28.png': set([
                (1, 1, 'UMarine'),
                (400, 400, 'Lime'),
            ]),
            'cool_002_2011-05-28.png': set([
                (160, 40, 'Turq'),
            ]),
        }

        # Same as expected_annotations, but for the points-only option.
        self.expected_points = {
            'cool_001_2011-05-28.png': set([
                (200, 300),
                (50, 250),
                (10, 10),
            ]),
            'cool_001_2012-05-28.png': set([
                (1, 1),
                (400, 400),
            ]),
            'cool_002_2011-05-28.png': set([
                (160, 40),
            ]),
        }

    def test_annotation_upload(self):

        annotation_text = self.annotation_file_contents_with_labels
        self.process_annotations_and_upload(
            annotation_text,
            self.image_filenames,
            self.expected_annotations_per_image,
            self.expected_annotations,
            is_uploading_annotations_not_just_points='yes'
        )

    def test_points_only_with_labels_in_file(self):

        annotation_text = self.annotation_file_contents_with_labels
        self.process_annotations_and_upload(
            annotation_text,
            self.image_filenames,
            self.expected_annotations_per_image,
            self.expected_points,
            is_uploading_annotations_not_just_points='no',
        )

    def test_points_only_without_labels_in_file(self):

        annotation_text = self.annotation_file_contents_without_labels
        self.process_annotations_and_upload(
            annotation_text,
            self.image_filenames,
            self.expected_annotations_per_image,
            self.expected_points,
            is_uploading_annotations_not_just_points='no',
        )

    def test_upload_an_image_with_zero_annotations_specified(self):

        annotation_text = self.annotation_file_contents_with_labels
        options = dict(
            is_uploading_points_or_annotations=True,
            is_uploading_annotations_not_just_points='no',
        )

        response_content = self.process_annotation_text(
            annotation_text,
            **options
        )

        # Run an image upload, avoiding most of the checks
        # that the other tests run.
        image_id, response = self.upload_image_test(
            os.path.join('2keys', 'rainbow_002_2012-05-28.png'),
            annotation_dict_id=response_content['annotation_dict_id'],
            **options
        )

        # Just check that the image fields are what we'd
        # expect for an image that doesn't have annotations
        # specified for it.  (i.e., it should have points
        # automatically generated.)
        img = Image.objects.get(pk=image_id)
        self.check_fields_for_non_annotation_upload(img)


class AnnotationUploadErrorTest(AnnotationUploadBaseTest):

    fixtures = ['test_users.yaml', 'test_labels.yaml',
                'test_labelsets.yaml', 'test_sources_with_labelsets.yaml']
    source_member_roles = [
        ('Labelset 2keys', 'user2', Source.PermTypes.ADMIN.code),
    ]

    def setUp(self):
        ClientTest.setUp(self)
        self.client.login(username='user2', password='secret')
        self.source_id = Source.objects.get(name='Labelset 2keys').pk

    def assert_annotation_file_error(self, response_content, line_num, line, error):
        self.assertEqual(response_content['status'], 'error')
        self.assertEqual(
            response_content['message'],
            str_consts.ANNOTATION_FILE_FULL_ERROR_MESSAGE_FMTSTR.format(
                line_num=line_num,
                line=line,
                error=error,
            )
        )
        if settings.UNIT_TEST_VERBOSITY >= 1:
            print "Annotation file error:\n{m}".format(m=response_content['message'])

    def test_annotations_on_and_no_annotation_dict_id(self):
        """
        Annotation upload is on, but no annotation dict identifier was
        passed into the upload function.

        A corner case that the client side code should prevent,
        but it's worth a test anyway.
        """
        options = dict(
            is_uploading_points_or_annotations=True,
        )

        image_id, response = self.upload_image(
            os.path.join('2keys', 'rainbow_002_2012-05-28.png'),
            **options
        )

        response_json = response.json()
        self.assertEqual(response_json['status'], 'error')
        self.assertEqual(response_json['message'], str_consts.UPLOAD_ANNOTATIONS_ON_AND_NO_ANNOTATION_DICT_ERROR_STR)

    def test_shelved_annotation_file_is_missing(self):
        """
        Annotation upload is on, and an annotation dict identifier was
        passed in, but no shelved annotation file with that identifier
        exists.

        A corner case that the client side code should prevent,
        but it's worth a test anyway.
        """
        pass #TODO

    def test_token_count_error(self):
        # Labels expected, too few tokens
        line = "cool; 001; 2011; 200; 300"
        response_content = self.process_annotation_text(
            line,
            is_uploading_points_or_annotations=True,
            is_uploading_annotations_not_just_points='yes',
        )
        self.assert_annotation_file_error(
            response_content,
            line_num="1", line=line,
            error=str_consts.ANNOTATION_FILE_TOKEN_COUNT_ERROR_FMTSTR.format(
                num_words_expected=6,
                num_words_found=5,
            )
        )

        # Labels expected, too many tokens
        line = "cool; 001; 2011; 200; 300; Scarlet; UMarine"
        response_content = self.process_annotation_text(
            line,
            is_uploading_points_or_annotations=True,
            is_uploading_annotations_not_just_points='yes',
        )
        self.assert_annotation_file_error(
            response_content,
            line_num="1", line=line,
            error=str_consts.ANNOTATION_FILE_TOKEN_COUNT_ERROR_FMTSTR.format(
                num_words_expected=6,
                num_words_found=7,
            )
        )

        # Labels not expected, too few tokens
        line = "cool; 001; 2011; 200"
        response_content = self.process_annotation_text(
            line,
            is_uploading_points_or_annotations=True,
            is_uploading_annotations_not_just_points='no',
        )
        self.assert_annotation_file_error(
            response_content,
            line_num="1",  line=line,
            error=str_consts.ANNOTATION_FILE_TOKEN_COUNT_ERROR_FMTSTR.format(
                num_words_expected=5,
                num_words_found=4,
            )
        )

        # Labels not expected, too few tokens
        line = "cool; 001; 2011; 200; 300; Scarlet; UMarine"
        response_content = self.process_annotation_text(
            line,
            is_uploading_points_or_annotations=True,
            is_uploading_annotations_not_just_points='no',
        )
        self.assert_annotation_file_error(
            response_content,
            line_num="1", line=line,
            error=str_consts.ANNOTATION_FILE_TOKEN_COUNT_ERROR_FMTSTR.format(
                num_words_expected=5,
                num_words_found=7,
            )
        )

    def test_row_col_not_a_number(self):
        line_A = "cool; 001; 2011; 123abc; 300; Scarlet"
        line_B = "cool; 001; 2011; 200; def; Scarlet"

        options = dict(
            is_uploading_points_or_annotations=True,
            is_uploading_annotations_not_just_points='yes',
        )

        response_content = self.process_annotation_text(
            line_A, **options
        )
        self.assert_annotation_file_error(
            response_content,
            line_num="1", line=line_A,
            error=str_consts.ANNOTATION_FILE_ROW_NOT_POSITIVE_INT_ERROR_FMTSTR.format(
                row='123abc',
            )
        )

        response_content = self.process_annotation_text(
            line_B, **options
        )
        self.assert_annotation_file_error(
            response_content,
            line_num="1", line=line_B,
            error=str_consts.ANNOTATION_FILE_COL_NOT_POSITIVE_INT_ERROR_FMTSTR.format(
                column='def',
            )
        )

    def test_row_col_not_an_integer(self):
        line_A = "cool; 001; 2011; 123.0; 300; Scarlet"
        line_B = "cool; 001; 2011; 200; 0.78; Scarlet"

        options = dict(
            is_uploading_points_or_annotations=True,
            is_uploading_annotations_not_just_points='yes',
        )

        response_content = self.process_annotation_text(
            line_A, **options
        )
        self.assert_annotation_file_error(
            response_content,
            line_num="1", line=line_A,
            error=str_consts.ANNOTATION_FILE_ROW_NOT_POSITIVE_INT_ERROR_FMTSTR.format(
                row='123.0',
            )
        )

        response_content = self.process_annotation_text(
            line_B, **options
        )
        self.assert_annotation_file_error(
            response_content,
            line_num="1", line=line_B,
            error=str_consts.ANNOTATION_FILE_COL_NOT_POSITIVE_INT_ERROR_FMTSTR.format(
                column='0.78',
            )
        )

    def test_row_col_not_a_positive_integer(self):
        line_A = "cool; 001; 2011; 0; 300; Scarlet"
        line_B = "cool; 001; 2011; 200; -10; Scarlet"

        options = dict(
            is_uploading_points_or_annotations=True,
            is_uploading_annotations_not_just_points='yes',
        )

        response_content = self.process_annotation_text(
            line_A, **options
        )
        self.assert_annotation_file_error(
            response_content,
            line_num="1", line=line_A,
            error=str_consts.ANNOTATION_FILE_ROW_NOT_POSITIVE_INT_ERROR_FMTSTR.format(
                row='0',
            )
        )

        response_content = self.process_annotation_text(
            line_B, **options
        )
        self.assert_annotation_file_error(
            response_content,
            line_num="1", line=line_B,
            error=str_consts.ANNOTATION_FILE_COL_NOT_POSITIVE_INT_ERROR_FMTSTR.format(
                column='-10',
            )
        )

    def test_label_not_in_database(self):
        line = "cool; 001; 2011; 200; 300; Yellow"
        response_content = self.process_annotation_text(
            line,
            is_uploading_points_or_annotations=True,
            is_uploading_annotations_not_just_points='yes',
        )
        self.assert_annotation_file_error(
            response_content,
            line_num="1", line=line,
            error=str_consts.ANNOTATION_FILE_LABEL_NOT_IN_DATABASE_ERROR_FMTSTR.format(
                label_code='Yellow',
            )
        )

    def test_label_not_in_labelset(self):
        line = "cool; 001; 2011; 200; 300; Forest"
        response_content = self.process_annotation_text(
            line,
            is_uploading_points_or_annotations=True,
            is_uploading_annotations_not_just_points='yes',
        )
        self.assert_annotation_file_error(
            response_content,
            line_num="1", line=line,
            error=str_consts.ANNOTATION_FILE_LABEL_NOT_IN_LABELSET_ERROR_FMTSTR.format(
                label_code='Forest',
            )
        )

    def test_invalid_year(self):
        line = "cool; 001; 04-26-2011; 200; 300; Scarlet"
        response_content = self.process_annotation_text(
            line,
            is_uploading_points_or_annotations=True,
            is_uploading_annotations_not_just_points='yes',
        )
        self.assert_annotation_file_error(
            response_content,
            line_num="1", line=line,
            error=str_consts.ANNOTATION_FILE_YEAR_ERROR_FMTSTR.format(
                year='04-2',
            )
        )
