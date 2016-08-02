import json
from urllib import urlencode
import datetime
from django.core.urlresolvers import reverse
from lib.test_utils import ClientTest
from images.models import Source, Image


class BrowseTest(ClientTest):
    """
    Test the browse page.
    """
    fixtures = ['test_users.yaml', 'test_labels.yaml', 'test_sources.yaml']
    source_member_roles = [
        ('private1', 'user2', Source.PermTypes.EDIT.code),
        ('private1', 'user3', Source.PermTypes.VIEW.code),
    ]

    def setUp(self):
        super(BrowseTest, self).setUp()
        self.source_id = Source.objects.get(name='private1').pk

        # Upload an image
        self.client.login(username='user2', password='secret')
        self.image_id = self.upload_image('001_2012-05-01_color-grid-001.png')[0]
        self.client.logout()

    def test_load_page_private_anonymous(self):
        """
        Load the private source's browse page while logged out ->
        sorry, don't have permission.
        """
        url = reverse('visualize_source', kwargs=dict(source_id=self.source_id))

        response = self.client.get(url)
        self.assertStatusOK(response)
        self.assertTemplateUsed(response, self.PERMISSION_DENIED_TEMPLATE)

    def test_load_page_private_as_source_outsider(self):
        """
        Load the page as a user outside the private source ->
        sorry, don't have permission.
        """
        self.client.login(username='user4', password='secret')
        url = reverse('visualize_source', kwargs=dict(source_id=self.source_id))

        response = self.client.get(url)
        self.assertStatusOK(response)
        self.assertTemplateUsed(response, self.PERMISSION_DENIED_TEMPLATE)

    def test_load_page_private_as_source_viewer(self):
        """
        Load the page as a source member with view permissions -> can load.
        """
        self.client.login(username='user3', password='secret')
        url = reverse('visualize_source', kwargs=dict(source_id=self.source_id))

        response = self.client.get(url)
        self.assertStatusOK(response)
        self.assertTemplateUsed(response, 'visualization/visualize_source.html')

        # Should have 1 image
        self.assertEqual(response.context['num_of_total_results'], 1)

    # TODO: Test filtering of results
    # TODO: Test indication of image statuses
    # TODO: Test pagination. An idea here is to reduce the results per page
    # to speed up testing, but not sure how.
    # Consider putting these in a separate test class(es).


class MetadataEditTest(ClientTest):
    """
    Test the metadata edit functionality.
    """
    @classmethod
    def setUpTestData(cls):
        super(MetadataEditTest, cls).setUpTestData()

        cls.user = cls.create_user()

        cls.source = cls.create_source(cls.user)

        cls.user_editor = cls.create_user()
        cls.add_source_member(cls.user, cls.source,
            cls.user_editor, Source.PermTypes.EDIT.code)
        cls.user_viewer = cls.create_user()
        cls.add_source_member(cls.user, cls.source,
            cls.user_viewer, Source.PermTypes.VIEW.code)

        cls.img1 = cls.upload_image_new(cls.user, cls.source)
        cls.img2 = cls.upload_image_new(cls.user, cls.source)

    def test_load_page_private_as_source_viewer(self):
        """
        Load the page as a source member with view permissions ->
        images view, and say invalid search parameters.
        TODO: Honestly, this is kind of weird. "Don't have permission"
        makes more sense.
        Perhaps images, metadata, patches should actually have
        different URLs, and depending on the radio button value it should
        redirect to the right URL. This'll also easier permission controls.
        """
        url = (
            reverse('visualize_source', kwargs=dict(source_id=self.source.pk))
            + '?' + urlencode(dict(page_view='metadata'))
        )

        self.client.force_login(self.user_viewer)
        response = self.client.get(url)

        self.assertStatusOK(response)
        self.assertTemplateUsed(response, 'visualization/visualize_source.html')
        self.assertMessages(response, ["Error: invalid search parameters."])
        self.assertEqual(response.context['metadata_formset'], None)

    def test_load_page(self):
        """
        Load the page as a source member with edit permissions -> can load.
        Also ensure the metadata form is there.
        """
        url = (
            reverse('visualize_source', kwargs=dict(source_id=self.source.pk))
            + '?' + urlencode(dict(page_view='metadata'))
        )

        self.client.force_login(self.user_editor)
        response = self.client.get(url)

        self.assertStatusOK(response)
        self.assertTemplateUsed(response, 'visualization/visualize_source.html')
        self.assertNotEqual(response.context['metadata_formset'], None)

    def test_load_page_no_images(self):
        """
        Load the page with no image results.
        """
        # First, assign enough metadata so it's possible to do a valid search
        # which gets no results.
        self.img1.metadata.aux1 = "1"
        self.img1.metadata.aux2 = "A"
        self.img1.metadata.save()
        self.img2.metadata.aux1 = "2"
        self.img2.metadata.aux2 = "B"
        self.img2.metadata.save()

        # We have one image with "1" "A", and another with "2" "B", so
        # searching for "1" "B" should get no results.
        url = (
            reverse('visualize_source', kwargs=dict(source_id=self.source.pk))
            + '?' + urlencode(dict(page_view='metadata', aux1="1", aux2="B"))
        )

        self.client.force_login(self.user)
        response = self.client.get(url)

        self.assertStatusOK(response)
        self.assertContains(response, "No image results.")

    def test_load_form(self):
        """
        See if the form is loaded with the correct metadata in the fields.
        """
        # We'll test various fields, and ensure that there is at least one
        # field where the two images have different non-empty values.
        self.img1.metadata.photo_date = datetime.date(2015,11,15)
        self.img1.metadata.aux1 = "1"
        self.img1.metadata.aux2 = "A"
        self.img1.metadata.framing = "Framing device FD-09"
        self.img1.metadata.save()
        self.img2.metadata.aux1 = "2"
        self.img2.metadata.aux2 = "B"
        self.img2.metadata.height_in_cm = 45
        self.img2.metadata.latitude = '-20.98'
        self.img2.metadata.camera = "Nikon"
        self.img2.metadata.save()

        url = (
            reverse('visualize_source', kwargs=dict(source_id=self.source.pk))
            + '?' + urlencode(dict(page_view='metadata'))
        )

        self.client.force_login(self.user)
        response = self.client.get(url)

        # The form should have the correct metadata for both images.
        formset = response.context['metadata_formset']

        metadata_pks_to_forms = dict()
        for form in formset.forms:
            metadata_pks_to_forms[form['id'].value()] = form

        img1_form = metadata_pks_to_forms[self.img1.pk]
        img2_form = metadata_pks_to_forms[self.img2.pk]

        self.assertEqual(img1_form['name'].value(), self.img1.metadata.name)
        self.assertEqual(img1_form['photo_date'].value(),
            datetime.date(2015,11,15))
        self.assertEqual(img1_form['aux1'].value(), "1")
        self.assertEqual(img1_form['aux2'].value(), "A")
        self.assertEqual(img1_form['framing'].value(), "Framing device FD-09")

        self.assertEqual(img2_form['name'].value(), self.img2.metadata.name)
        self.assertEqual(img2_form['aux1'].value(), "2")
        self.assertEqual(img2_form['aux2'].value(), "B")
        self.assertEqual(img2_form['height_in_cm'].value(), 45)
        self.assertEqual(img2_form['latitude'].value(), "-20.98")
        self.assertEqual(img2_form['camera'].value(), "Nikon")

    def test_submit_edits(self):
        """
        Submit metadata edits and see if they go through.
        """
        url = (reverse('metadata_edit_ajax', kwargs=dict(
            source_id=self.source.pk
        )))

        self.client.force_login(self.user)

        # The ajax view doesn't care about setting up a valid search.
        # As long as the number-of-forms fields match the actual form data,
        # it's fine.
        post_data = {
            'form-TOTAL_FORMS': 1,
            'form-INITIAL_FORMS': 1,
            'form-MAX_NUM_FORMS': '',
            'form-0-id': self.img1.metadata.pk,
            'form-0-name': 'new_name.arbitrary_ext',
            'form-0-photo_date': '2004-07-19',
            'form-0-height_in_cm': 325,
            'form-0-latitude': '68',
            'form-0-longitude': '-25.908',
            'form-0-depth': "57.1m",
            'form-0-camera': "Canon ABC94",
            'form-0-photographer': "",
            'form-0-water_quality': "",
            'form-0-strobes': "",
            'form-0-framing': "",
            'form-0-balance': "Balance card A",
        }
        response = self.client.post(url, post_data)

        # Response should be as expected.
        self.assertStatusOK(response)
        response_json = response.json()
        self.assertEqual(response_json['status'], 'success')

        self.img1.metadata.refresh_from_db()
        self.assertEqual('new_name.arbitrary_ext', self.img1.metadata.name)
        self.assertEqual(datetime.date(2004,7,19), self.img1.metadata.photo_date)
        self.assertEqual(325, self.img1.metadata.height_in_cm)
        self.assertEqual('68', self.img1.metadata.latitude)
        self.assertEqual('-25.908', self.img1.metadata.longitude)
        self.assertEqual("57.1m", self.img1.metadata.depth)
        self.assertEqual("Canon ABC94", self.img1.metadata.camera)
        self.assertEqual("", self.img1.metadata.photographer)
        self.assertEqual("", self.img1.metadata.water_quality)
        self.assertEqual("", self.img1.metadata.strobes)
        self.assertEqual("", self.img1.metadata.framing)
        self.assertEqual("Balance card A", self.img1.metadata.balance)

    def test_submit_errors(self):
        """
        Submit metadata edits with errors.

        Ensure that valid edits in the same submission don't get saved,
        and ensure the error messages are as expected.
        """
        url = (reverse('metadata_edit_ajax', kwargs=dict(
            source_id=self.source.pk
        )))

        self.client.force_login(self.user)

        post_data = {
            'form-TOTAL_FORMS': 2,
            'form-INITIAL_FORMS': 2,
            'form-MAX_NUM_FORMS': '',
            'form-0-id': self.img1.metadata.pk,
            'form-0-name': self.img1.metadata.name,
            'form-0-photo_date': '2007-04-08',    # Valid edit
            'form-0-height_in_cm': '',
            'form-0-latitude': '',
            'form-0-longitude': '',
            'form-0-depth': "",
            'form-0-camera': "",
            'form-0-photographer': "",
            'form-0-water_quality': "",
            'form-0-strobes': "",
            'form-0-framing': "",
            'form-0-balance': "",
            'form-1-id': self.img2.metadata.pk,
            'form-1-name': self.img2.metadata.name,
            'form-1-photo_date': '205938',    # Not valid
            'form-1-height_in_cm': '-20',    # Not valid
            'form-1-latitude': '',
            'form-1-longitude': '',
            'form-1-depth': "",
            'form-1-camera': "",
            'form-1-photographer': "",
            'form-1-water_quality': "",
            'form-1-strobes': "",
            'form-1-framing': "",
            'form-1-balance': "Balance card A",    # Valid edit
        }
        response = self.client.post(url, post_data)

        # Response should be as expected.
        self.assertStatusOK(response)
        response_json = response.json()
        self.assertEqual(response_json['status'], 'error')

        # Response errors should be as expected.
        # The error order is undefined, so we won't check for order.
        response_error_dict = dict([
            (e['fieldId'], e['errorMessage'])
            for e in response_json['errors']
        ])
        expected_error_dict = dict()
        expected_error_dict['id_form-1-photo_date'] = self.img2.metadata.name \
             + " | Date" \
             + " | Enter a valid date."
        expected_error_dict['id_form-1-height_in_cm'] = self.img2.metadata.name \
             + " | Height (cm)" \
             + " | Ensure this value is greater than or equal to 1."
        self.assertDictEqual(
            response_error_dict,
            expected_error_dict,
        )

        # No edits should have gone through.
        self.img1.metadata.refresh_from_db()
        self.img2.metadata.refresh_from_db()
        self.assertEqual(self.img1.metadata.photo_date, None)
        self.assertEqual(self.img2.metadata.balance, "")

    def test_dupe_name_errors(self):
        """
        Submit metadata edits with duplicate-image-name errors.
        """
        self.img3 = self.upload_image_new(self.user, self.source)
        self.img4 = self.upload_image_new(self.user, self.source)
        self.img5 = self.upload_image_new(self.user, self.source)

        url = (reverse('metadata_edit_ajax', kwargs=dict(
            source_id=self.source.pk
        )))

        self.client.force_login(self.user)

        post_data = {
            'form-TOTAL_FORMS': 4,
            'form-INITIAL_FORMS': 4,
            'form-MAX_NUM_FORMS': '',

            'form-0-id': self.img1.metadata.pk,
            # Dupe with img5, which is not in the form
            'form-0-name': self.img5.metadata.name,
            'form-0-photo_date': '2007-04-08',
            'form-0-height_in_cm': '',
            'form-0-latitude': '',
            'form-0-longitude': '',
            'form-0-depth': "",
            'form-0-camera': "",
            'form-0-photographer': "",
            'form-0-water_quality': "",
            'form-0-strobes': "",
            'form-0-framing': "",
            'form-0-balance': "",

            'form-1-id': self.img2.metadata.pk,
            # Dupe with img3, which is also in the form
            'form-1-name': 'new_name_23',
            'form-1-photo_date': '2007-04-08',
            'form-1-height_in_cm': '',
            'form-1-latitude': '',
            'form-1-longitude': '',
            'form-1-depth': "",
            'form-1-camera': "",
            'form-1-photographer': "",
            'form-1-water_quality': "",
            'form-1-strobes': "",
            'form-1-framing': "",
            'form-1-balance': "",

            'form-2-id': self.img3.metadata.pk,
            # Dupe with img2, which is also in the form
            'form-2-name': 'new_name_23',
            'form-2-photo_date': '2007-04-08',
            'form-2-height_in_cm': '',
            'form-2-latitude': '',
            'form-2-longitude': '',
            'form-2-depth': "",
            'form-2-camera': "",
            'form-2-photographer': "",
            'form-2-water_quality': "",
            'form-2-strobes': "",
            'form-2-framing': "",
            'form-2-balance': "",

            'form-3-id': self.img4.metadata.pk,
            # Not dupe
            'form-3-name': 'new_name_4',
            'form-3-photo_date': '2007-04-08',
            'form-3-height_in_cm': '',
            'form-3-latitude': '',
            'form-3-longitude': '',
            'form-3-depth': "",
            'form-3-camera': "",
            'form-3-photographer': "",
            'form-3-water_quality': "",
            'form-3-strobes': "",
            'form-3-framing': "",
            'form-3-balance': "",
        }
        response = self.client.post(url, post_data)

        # Response should be as expected.
        self.assertStatusOK(response)
        response_json = response.json()
        self.assertEqual(response_json['status'], 'error')

        # Response errors should be as expected.
        # The error order is undefined, so we won't check for order.
        response_error_dict = dict([
            (e['fieldId'], e['errorMessage'])
            for e in response_json['errors']
        ])
        expected_error_dict = dict()
        expected_error_dict['id_form-0-name'] = (
            self.img5.metadata.name
            + " | Name"
            + " | Same name as another image in the source or this form"
        )
        expected_error_dict['id_form-1-name'] = (
            'new_name_23'
            + " | Name"
            + " | Same name as another image in the source or this form"
        )
        expected_error_dict['id_form-2-name'] = (
            'new_name_23'
            + " | Name"
            + " | Same name as another image in the source or this form"
        )
        self.assertDictEqual(
            response_error_dict,
            expected_error_dict,
        )

        # No edits should have gone through.
        self.img4.metadata.refresh_from_db()
        self.assertEqual(self.img4.metadata.photo_date, None)


class ImageDeleteTest(ClientTest):
    """
    Test the image delete functionality.
    """
    fixtures = ['test_users.yaml', 'test_labels.yaml', 'test_sources.yaml']
    source_member_roles = [
        ('private1', 'user2', Source.PermTypes.EDIT.code),
        ('private1', 'user3', Source.PermTypes.VIEW.code),
    ]

    def setUp(self):
        super(ImageDeleteTest, self).setUp()
        self.source_id = Source.objects.get(name='private1').pk

        # Upload images
        self.client.login(username='user2', password='secret')
        self.image_id = \
            self.upload_image('001_2012-05-01_color-grid-001.png')[0]
        self.image_id_2 = \
            self.upload_image('002_2012-06-28_color-grid-002.png')[0]
        self.image_id_3 = \
            self.upload_image('003_2012-06-28_color-grid-003.png')[0]

        # Change metadata
        img1 = Image.objects.get(pk=self.image_id)
        img1.metadata.aux1 = '001'
        img1.metadata.save()
        img2 = Image.objects.get(pk=self.image_id_2)
        img2.metadata.aux1 = '002'
        img2.metadata.save()
        img3 = Image.objects.get(pk=self.image_id_3)
        img3.metadata.aux1 = '003'
        img3.metadata.save()

        self.client.logout()

    def test_submit_private_as_source_viewer(self):
        """
        Submit deletion to private source as a source viewer ->
        sorry, don't have permission to access this page.
        Technically not a page, just a view, but still makes enough
        sense considering that a viewer-level user can only get here
        by URL typing.
        """
        self.client.login(username='user3', password='secret')
        url = reverse('browse_delete', kwargs=dict(source_id=self.source_id))

        response = self.client.get(url)
        self.assertStatusOK(response)
        self.assertTemplateUsed(response, self.PERMISSION_DENIED_TEMPLATE)

    def test_load_page_private_as_source_editor(self):
        """
        Submit deletion to private source as a source editor ->
        deletion processed normally.
        """
        self.client.login(username='user2', password='secret')
        url = reverse('browse_delete', kwargs=dict(source_id=self.source_id))

        response = self.client.post(url)
        self.assertRedirects(
            response,
            reverse('visualize_source', kwargs=dict(source_id=self.source_id)))

    def test_delete_all_images(self):
        """
        Delete all images in the source.
        """
        self.client.login(username='user2', password='secret')
        url = reverse('browse_delete', kwargs=dict(source_id=self.source_id))

        # Delete.
        self.client.post(url, dict(
            specify_method='search_keys', specify_str=json.dumps(dict())))
        # Check that the images were deleted.
        self.assertRaises(
            Image.DoesNotExist, Image.objects.get, pk=self.image_id)
        self.assertRaises(
            Image.DoesNotExist, Image.objects.get, pk=self.image_id_2)
        self.assertRaises(
            Image.DoesNotExist, Image.objects.get, pk=self.image_id_3)
        # TODO: Check another source and ensure its images weren't deleted.

    def test_delete_by_location_value(self):
        """
        Delete images by aux. meta.
        """
        self.client.login(username='user2', password='secret')
        url = reverse('browse_delete', kwargs=dict(source_id=self.source_id))

        specify_str_dict = dict()
        specify_str_dict['aux1'] = '001'
        self.client.post(url, dict(
            specify_method='search_keys',
            specify_str=json.dumps(specify_str_dict),
        ))

        # Check that we can get image 002 and 003, but not 001,
        # which we chose to delete.
        self.assertRaises(
            Image.DoesNotExist, Image.objects.get, pk=self.image_id)
        Image.objects.get(pk=self.image_id_2)
        Image.objects.get(pk=self.image_id_3)
        # TODO: Test other filters besides aux1.

    def test_delete_by_image_ids(self):
        """
        Delete images of particular image ids.
        """
        self.client.login(username='user2', password='secret')
        url = reverse('browse_delete', kwargs=dict(source_id=self.source_id))

        image_ids = \
            ','.join(str(pk) for pk in [self.image_id, self.image_id_3])
        self.client.post(url, dict(
            specify_method='image_ids',
            specify_str=image_ids,
        ))

        # Check that we can get image 002, but not 001 and 003,
        # which we chose to delete.
        self.assertRaises(
            Image.DoesNotExist, Image.objects.get, pk=self.image_id)
        Image.objects.get(pk=self.image_id_2)
        self.assertRaises(
            Image.DoesNotExist, Image.objects.get, pk=self.image_id_3)

