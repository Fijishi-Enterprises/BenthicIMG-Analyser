import datetime

from django.urls import reverse

from lib.tests.utils import BasePermissionTest, ClientTest


class PermissionTest(BasePermissionTest):
    """
    Test page permissions.
    """
    def test_edit_metadata(self):
        url = reverse('edit_metadata', args=[self.source.pk])
        template = 'visualization/edit_metadata.html'

        self.source_to_private()
        self.assertPermissionLevel(url, self.SOURCE_EDIT, template=template)
        self.source_to_public()
        self.assertPermissionLevel(url, self.SOURCE_EDIT, template=template)

    def test_edit_metadata_ajax(self):
        url = reverse('edit_metadata_ajax', args=[self.source.pk])

        # We get a 500 error if we don't pass in basic formset params and at
        # least 1 form.
        img = self.upload_image(self.user, self.source)
        post_data = {
            'form-TOTAL_FORMS': 1,
            'form-INITIAL_FORMS': 1,
            'form-MAX_NUM_FORMS': '',
            'form-0-id': img.metadata.pk,
        }

        self.source_to_private()
        self.assertPermissionLevel(
            url, self.SOURCE_EDIT, is_json=True, post_data=post_data)
        self.source_to_public()
        self.assertPermissionLevel(
            url, self.SOURCE_EDIT, is_json=True, post_data=post_data)


class LoadPageTest(ClientTest):
    """
    Test the metadata edit functionality.
    """
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()

        cls.user = cls.create_user()
        cls.source = cls.create_source(cls.user)
        cls.img1 = cls.upload_image(cls.user, cls.source)
        cls.img2 = cls.upload_image(cls.user, cls.source)
        cls.img3 = cls.upload_image(cls.user, cls.source)
        cls.url = reverse('edit_metadata', args=[cls.source.pk])

        cls.default_search_params = dict(
            image_form_type='search',
            aux1='', aux2='', aux3='', aux4='', aux5='',
            height_in_cm='', latitude='', longitude='', depth='',
            photographer='', framing='', balance='',
            photo_date_0='', photo_date_1='', photo_date_2='',
            photo_date_3='', photo_date_4='',
            image_name='', annotation_status='',
            last_annotated_0='', last_annotated_1='', last_annotated_2='',
            last_annotated_3='', last_annotated_4='',
            last_annotator_0='', last_annotator_1='',
        )

    def test_page_landing(self):
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        self.assertEqual(response.context['num_images'], 3)

    def test_search(self):
        self.img1.metadata.aux1 = 'SiteA'
        self.img1.metadata.save()

        post_data = self.default_search_params.copy()
        post_data['aux1'] = 'SiteA'

        self.client.force_login(self.user)
        response = self.client.post(self.url, post_data)
        self.assertEqual(response.context['num_images'], 1)

    def test_image_ids(self):
        post_data = dict(
            image_form_type='ids',
            ids=','.join([str(self.img2.pk), str(self.img3.pk)])
        )

        self.client.force_login(self.user)
        response = self.client.post(self.url, post_data)
        self.assertEqual(response.context['num_images'], 2)

    def test_ignore_image_ids_of_other_sources(self):
        source2 = self.create_source(self.user)
        s2_img = self.upload_image(self.user, source2)

        # 1 image from this source, 1 image from another source
        post_data = dict(
            image_form_type='ids',
            ids=','.join([str(self.img1.pk), str(s2_img.pk)])
        )

        self.client.force_login(self.user)
        response = self.client.post(self.url, post_data)
        self.assertEqual(response.context['num_images'], 1)

    def test_non_integer_image_ids(self):
        post_data = dict(
            image_form_type='ids',
            ids=','.join([str(self.img2.pk), 'abc'])
        )

        self.client.force_login(self.user)
        response = self.client.post(self.url, post_data)
        self.assertContains(response, "Search parameters were invalid.")

    def test_zero_images(self):
        post_data = self.default_search_params.copy()
        post_data['photo_date_0'] = 'date'
        post_data['photo_date_2'] = datetime.date(2000, 1, 1)

        self.client.force_login(self.user)
        response = self.client.post(self.url, post_data)
        self.assertEqual(response.context['num_images'], 0)
        self.assertContains(response, "No image results.")

    def test_load_form(self):
        """
        See if the form is loaded with the correct metadata in the fields.
        """
        # We'll test various fields, and ensure that there is at least one
        # field where the two images have different non-empty values.
        self.img1.metadata.photo_date = datetime.date(2015, 11, 15)
        self.img1.metadata.aux1 = "1"
        self.img1.metadata.aux2 = "A"
        self.img1.metadata.framing = "Framing device FD-09"
        self.img1.metadata.save()
        self.img2.metadata.aux1 = "2"
        self.img2.metadata.aux2 = "B"
        self.img2.metadata.height_in_cm = 45
        self.img2.metadata.latitude = '-20.98'
        self.img2.metadata.camera = "Nikon"
        self.img2.metadata.comments = "This, is; a< test/\ncomment."
        self.img2.metadata.save()

        self.client.force_login(self.user)
        response = self.client.get(self.url)

        # The form should have the correct metadata for both images.
        formset = response.context['metadata_formset']

        metadata_pks_to_forms = dict()
        for form in formset.forms:
            metadata_pks_to_forms[form['id'].value()] = form

        img1_form = metadata_pks_to_forms[self.img1.pk]
        img2_form = metadata_pks_to_forms[self.img2.pk]

        self.assertEqual(img1_form['name'].value(), self.img1.metadata.name)
        self.assertEqual(
            img1_form['photo_date'].value(), datetime.date(2015, 11, 15))
        self.assertEqual(img1_form['aux1'].value(), "1")
        self.assertEqual(img1_form['aux2'].value(), "A")
        self.assertEqual(img1_form['framing'].value(), "Framing device FD-09")

        self.assertEqual(img2_form['name'].value(), self.img2.metadata.name)
        self.assertEqual(img2_form['aux1'].value(), "2")
        self.assertEqual(img2_form['aux2'].value(), "B")
        self.assertEqual(img2_form['height_in_cm'].value(), 45)
        self.assertEqual(img2_form['latitude'].value(), "-20.98")
        self.assertEqual(img2_form['camera'].value(), "Nikon")
        self.assertEqual(
            img2_form['comments'].value(), "This, is; a< test/\ncomment.")


class SubmitEditsTest(ClientTest):
    """
    Test the metadata edit functionality.
    """
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()

        cls.user = cls.create_user()
        cls.source = cls.create_source(cls.user)
        cls.img1 = cls.upload_image(cls.user, cls.source)
        cls.img2 = cls.upload_image(cls.user, cls.source)
        cls.img3 = cls.upload_image(cls.user, cls.source)
        cls.img4 = cls.upload_image(cls.user, cls.source)
        cls.img5 = cls.upload_image(cls.user, cls.source)
        cls.url = reverse('edit_metadata_ajax', args=[cls.source.pk])

    def test_submit_edits(self):
        """
        Submit metadata edits and see if they go through.
        """
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
            'form-0-comments': "These, are; some<\n test/ comments.",
        }

        self.client.force_login(self.user)
        response = self.client.post(self.url, post_data)

        # Response should be as expected.
        self.assertStatusOK(response)
        response_json = response.json()
        self.assertEqual(response_json['status'], 'success')

        self.img1.metadata.refresh_from_db()
        self.assertEqual('new_name.arbitrary_ext', self.img1.metadata.name)
        self.assertEqual(
            datetime.date(2004, 7, 19), self.img1.metadata.photo_date)
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
        self.assertEqual(
            "These, are; some<\n test/ comments.", self.img1.metadata.comments)

    def test_submit_errors(self):
        """
        Submit metadata edits with errors.

        Ensure that valid edits in the same submission don't get saved,
        and ensure the error messages are as expected.
        """
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
            'form-0-comments': "",
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
            'form-1-comments': "",
        }

        self.client.force_login(self.user)
        response = self.client.post(self.url, post_data)

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
        expected_error_dict['id_form-1-photo_date'] = (
            self.img2.metadata.name
            + " | Date"
            + " | Enter a valid date.")
        expected_error_dict['id_form-1-height_in_cm'] = (
            self.img2.metadata.name
            + " | Height (cm)"
            + " | Ensure this value is greater than or equal to 0.")
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
            'form-0-comments': "",

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
            'form-1-comments': "",

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
            'form-2-comments': "",

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
            'form-3-comments': "",
        }

        self.client.force_login(self.user)
        response = self.client.post(self.url, post_data)

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

    def test_error_messages_containing_unicode(self):
        """
        Ensure error messages containing Unicode characters can be processed
        properly. For example, include Unicode in an image's name and trigger
        an error for that image.
        """
        post_data = {
            'form-TOTAL_FORMS': 1,
            'form-INITIAL_FORMS': 1,
            'form-MAX_NUM_FORMS': '',
            'form-0-id': self.img1.metadata.pk,
            'form-0-name': 'あ.png',
            'form-0-photo_date': '2004',
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
            'form-0-comments': "These, are; some<\n test/ comments.",
        }

        self.client.force_login(self.user)
        response = self.client.post(self.url, post_data)
        response_json = response.json()

        # The error order is undefined, so we won't check for order.
        response_error_dict = dict([
            (e['fieldId'], e['errorMessage'])
            for e in response_json['errors']
        ])
        expected_error_dict = dict()
        expected_error_dict['id_form-0-photo_date'] = (
            "あ.png"
            + " | Date"
            + " | Enter a valid date."
        )
        self.assertDictEqual(response_error_dict, expected_error_dict)

    def test_deny_metadata_ids_of_other_source(self):
        """
        Attempts to submit metadata IDs of another source should be rejected.
        Otherwise there's a security hole.

        Specifically, what happens here is that the edits to the outside-ID
        object are ignored, and no error is returned. This is the expected
        behavior when an ID is outside of the Django formset's queryset.
        """
        source_2 = self.create_source(self.user)
        image_s2 = self.upload_image(self.user, source_2)
        old_name = image_s2.metadata.name

        post_data = {
            'form-TOTAL_FORMS': 1,
            'form-INITIAL_FORMS': 1,
            'form-MAX_NUM_FORMS': '',
            # Metadata ID from another source
            'form-0-id': image_s2.metadata.pk,
            'form-0-name': 'other_source_image.png',
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
            'form-0-comments': "",
        }

        self.client.force_login(self.user)
        response = self.client.post(self.url, post_data)

        # Response should be as expected.
        self.assertStatusOK(response)
        response_json = response.json()
        self.assertEqual(response_json['status'], 'success')

        # No edits should have gone through.
        image_s2.metadata.refresh_from_db()
        self.assertEqual(image_s2.metadata.name, old_name)
        self.assertEqual(image_s2.metadata.photo_date, None)
