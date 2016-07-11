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
    fixtures = ['test_users.yaml', 'test_labels.yaml', 'test_sources.yaml']
    source_member_roles = [
        ('private1', 'user2', Source.PermTypes.EDIT.code),
        ('private1', 'user3', Source.PermTypes.VIEW.code),
    ]

    def setUp(self):
        super(MetadataEditTest, self).setUp()
        self.source_id = Source.objects.get(name='private1').pk

        # Upload an image
        self.client.login(username='user2', password='secret')
        self.image_id = \
            self.upload_image('001_2012-05-01_color-grid-001.png')[0]
        self.image_id_2 = \
            self.upload_image('001_2012-05-01_color-grid-001.png')[0]
        self.client.logout()

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
            reverse('visualize_source', kwargs=dict(source_id=self.source_id))
            + '?' + urlencode(dict(page_view='metadata'))
        )

        self.client.login(username='user3', password='secret')
        response = self.client.get(url)

        self.assertStatusOK(response)
        self.assertTemplateUsed(response, 'visualization/visualize_source.html')
        self.assertMessages(response, ["Error: invalid search parameters."])
        self.assertEqual(response.context['metadataForm'], None)

    def test_load_page(self):
        """
        Load the page as a source member with edit permissions -> can load.
        Also ensure the metadata form is there.
        """
        url = (
            reverse('visualize_source', kwargs=dict(source_id=self.source_id))
            + '?' + urlencode(dict(page_view='metadata'))
        )

        self.client.login(username='user2', password='secret')
        response = self.client.get(url)

        self.assertStatusOK(response)
        self.assertTemplateUsed(response, 'visualization/visualize_source.html')
        self.assertNotEqual(response.context['metadataForm'], None)

    def test_load_page_no_images(self):
        """
        Load the page with no image results.
        """
        # First, assign enough metadata so it's possible to do a valid search
        # which gets no results.
        img1 = Image.objects.get(pk=self.image_id)
        img1.metadata.aux1 = "1"
        img1.metadata.aux2 = "A"
        img1.metadata.save()
        img2 = Image.objects.get(pk=self.image_id_2)
        img2.metadata.aux1 = "2"
        img2.metadata.aux2 = "B"
        img2.metadata.save()

        url = (
            reverse('visualize_source', kwargs=dict(source_id=self.source_id))
            + '?' + urlencode(dict(
                page_view='metadata', aux1="1", aux2="B"))
        )

        self.client.login(username='user2', password='secret')
        response = self.client.get(url)

        self.assertStatusOK(response)
        self.assertContains(response, "No image results.")

    def test_load_form(self):
        """
        See if the form is loaded with the correct metadata in the fields.
        """
        # Just get one image so we can assume forms[0] is what we need.
        img1 = Image.objects.get(pk=self.image_id)
        img1.metadata.aux1 = "1"
        img1.metadata.save()
        url = (
            reverse('visualize_source', kwargs=dict(source_id=self.source_id))
            + '?' + urlencode(dict(page_view='metadata', aux1="1"))
        )

        self.client.login(username='user2', password='secret')
        response = self.client.get(url)

        # The form should have the correct metadata for the one image that
        # has been uploaded.
        form = response.context['metadataForm']
        image = Image.objects.get(pk=self.image_id)
        self.assertEqual(form.forms[0]['image_id'].value(), self.image_id)
        self.assertEqual(form.forms[0]['photo_date'].value(),
            image.metadata.photo_date)
        self.assertEqual(form.forms[0]['height_in_cm'].value(),
            image.metadata.height_in_cm)
        self.assertEqual(form.forms[0]['latitude'].value(),
            image.metadata.latitude)
        self.assertEqual(form.forms[0]['longitude'].value(),
            image.metadata.longitude)
        self.assertEqual(form.forms[0]['depth'].value(),
            image.metadata.depth)
        self.assertEqual(form.forms[0]['camera'].value(),
            image.metadata.camera)
        self.assertEqual(form.forms[0]['photographer'].value(),
            image.metadata.photographer)
        self.assertEqual(form.forms[0]['water_quality'].value(),
            image.metadata.water_quality)
        self.assertEqual(form.forms[0]['strobes'].value(),
            image.metadata.strobes)
        self.assertEqual(form.forms[0]['framing'].value(),
            image.metadata.framing)
        self.assertEqual(form.forms[0]['balance'].value(),
            image.metadata.balance)

    def test_submit_edits(self):
        """
        Submit metadata edits and see if they go through.
        """
        url = (reverse('metadata_edit_ajax', kwargs=dict(
            source_id=self.source_id
        )))

        self.client.login(username='user2', password='secret')

        image = Image.objects.get(pk=self.image_id)
        old_photographer = image.metadata.photographer
        old_water_quality = image.metadata.water_quality
        old_strobes = image.metadata.strobes
        old_framing = image.metadata.framing
        old_balance = image.metadata.balance
        post_data = {
            'form-TOTAL_FORMS': 1,
            'form-INITIAL_FORMS': 1,
            'form-MAX_NUM_FORMS': '',
            'form-0-image_id': self.image_id,
            'form-0-photo_date': '2004-07-19',
            'form-0-height_in_cm': 325,
            'form-0-latitude': '68',
            'form-0-longitude': '-25.908',
            'form-0-depth': "57.1m",
            'form-0-camera': "Canon ABC94",
            'form-0-photographer': old_photographer,
            'form-0-water_quality': old_water_quality,
            'form-0-strobes': old_strobes,
            'form-0-framing': old_framing,
            'form-0-balance': old_balance,
        }
        response = self.client.post(url, post_data)

        # Response should be as expected.
        self.assertStatusOK(response)
        response_json = response.json()
        self.assertEqual(response_json['status'], 'success')

        # The database should have the updated metadata for the image,
        # without affecting the non-updated metadata.
        image = Image.objects.get(pk=self.image_id)
        self.assertEqual(datetime.date(2004,7,19), image.metadata.photo_date)
        self.assertEqual(325, image.metadata.height_in_cm)
        self.assertEqual('68', image.metadata.latitude)
        self.assertEqual('-25.908', image.metadata.longitude)
        self.assertEqual("57.1m", image.metadata.depth)
        self.assertEqual("Canon ABC94", image.metadata.camera)
        self.assertEqual(old_photographer, image.metadata.photographer)
        self.assertEqual(old_water_quality, image.metadata.water_quality)
        self.assertEqual(old_strobes, image.metadata.strobes)
        self.assertEqual(old_framing, image.metadata.framing)
        self.assertEqual(old_balance, image.metadata.balance)


class MetadataEditTest2(ClientTest):
    """
    Test metadata edit, more specific functionality.
    """
    fixtures = ['test_users.yaml', 'test_labels.yaml',
        'test_sources_with_different_keys.yaml']
    source_member_roles = [
        ('5 keys', 'user2', Source.PermTypes.EDIT.code),
        ('5 keys', 'user3', Source.PermTypes.VIEW.code),
    ]

    def setUp(self):
        super(MetadataEditTest2, self).setUp()
        self.source_id = Source.objects.get(name='5 keys').pk

        self.default_upload_params['specify_metadata'] = 'after'

        # Upload an image
        self.client.login(username='user2', password='secret')
        self.image_id = self.upload_image('001_2012-05-01_color-grid-001.png')[0]
        self.client.logout()

    def test_load_image_with_incomplete_location_values(self):
        """
        Load the metadata form with an image that has value k but not
        value k-1. Value k should still display on the form.
        (Don't assume that k isn't there just because k-1 isn't.)
        """
        url = (
            reverse('visualize_source', kwargs=dict(source_id=self.source_id))
            + '?' + urlencode(dict(page_view='metadata'))
        )
        self.client.login(username='user2', password='secret')

        image = Image.objects.get(pk=self.image_id)
        image.metadata.aux1 = 'AAA'
        image.metadata.aux2 = ''
        image.metadata.aux3 = 'CCC'
        image.metadata.aux4 = 'DDD'
        image.metadata.aux5 = ''
        image.metadata.save()

        # Load the page with the metadata form.
        # Ensure that the location values filled are: 1, 3, 4
        response = self.client.get(url)
        form = response.context['metadataForm']
        self.assertEqual(form.forms[0]['aux1'].value(), 'AAA')
        self.assertEqual(form.forms[0]['aux2'].value(), '')
        self.assertEqual(form.forms[0]['aux3'].value(), 'CCC')
        self.assertEqual(form.forms[0]['aux4'].value(), 'DDD')
        self.assertEqual(form.forms[0]['aux5'].value(), '')


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
        Delete images of a particular location value.
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

