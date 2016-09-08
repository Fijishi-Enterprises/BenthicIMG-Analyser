from django.core.urlresolvers import reverse

from images.models import Source, Image, Metadata, ImageStatus
from lib.test_utils import ClientTest


class PermissionTest(ClientTest):
    """
    Test page permissions.
    """
    @classmethod
    def setUpTestData(cls):
        super(PermissionTest, cls).setUpTestData()

        cls.user = cls.create_user()

        cls.source = cls.create_source(cls.user)

        cls.user_editor = cls.create_user()
        cls.add_source_member(
            cls.user, cls.source, cls.user_editor, Source.PermTypes.EDIT.code)
        cls.user_viewer = cls.create_user()
        cls.add_source_member(
            cls.user, cls.source, cls.user_viewer, Source.PermTypes.VIEW.code)
        cls.user_outsider = cls.create_user()

        cls.img1 = cls.upload_image_new(cls.user, cls.source)

        cls.url = reverse('browse_delete_ajax', args=[cls.source.pk])

        cls.default_search_params = dict(
            image_form_type='search',
            aux1='', aux2='', aux3='', aux4='', aux5='',
            height_in_cm='', latitude='', longitude='', depth='',
            photographer='', framing='', balance='',
            date_filter_0='year', date_filter_1='',
            date_filter_2='', date_filter_3='',
            annotation_status='',
        )

    def test_load_page_as_anonymous(self):
        response = self.client.post(self.url, self.default_search_params)
        self.assertStatusOK(response)
        self.assertDictEqual(response.json(), dict(
            error=(
                "You don't have permission to access this part of this source."
            )
        ))
        # Since the images weren't deleted,
        # these image-getting statements should not raise errors.
        Image.objects.get(pk=self.img1.pk)

    def test_load_page_as_source_outsider(self):
        self.client.force_login(self.user_outsider)
        response = self.client.post(self.url, self.default_search_params)
        self.assertStatusOK(response)
        self.assertDictEqual(response.json(), dict(
            error=(
                "You don't have permission to access this part of this source."
            )
        ))
        Image.objects.get(pk=self.img1.pk)

    def test_load_page_as_source_viewer(self):
        self.client.force_login(self.user_viewer)
        response = self.client.post(self.url, self.default_search_params)
        self.assertStatusOK(response)
        self.assertDictEqual(response.json(), dict(
            error=(
                "You don't have permission to access this part of this source."
            )
        ))
        Image.objects.get(pk=self.img1.pk)

    def test_load_page_as_source_editor(self):
        self.client.force_login(self.user_editor)
        response = self.client.post(self.url, self.default_search_params)
        self.assertStatusOK(response)
        self.assertNotIn('error', response.json())


class SuccessTest(ClientTest):
    @classmethod
    def setUpTestData(cls):
        super(SuccessTest, cls).setUpTestData()

        cls.user = cls.create_user()
        cls.source = cls.create_source(cls.user)
        cls.img1 = cls.upload_image_new(cls.user, cls.source)
        cls.img2 = cls.upload_image_new(cls.user, cls.source)
        cls.img3 = cls.upload_image_new(cls.user, cls.source)

        cls.url = reverse('browse_delete_ajax', args=[cls.source.pk])

        cls.default_search_params = dict(
            image_form_type='search',
            aux1='', aux2='', aux3='', aux4='', aux5='',
            height_in_cm='', latitude='', longitude='', depth='',
            photographer='', framing='', balance='',
            date_filter_0='year', date_filter_1='',
            date_filter_2='', date_filter_3='',
            annotation_status='',
        )

    def test_delete_all_images(self):
        """
        Delete all images in the source.
        """
        self.client.force_login(self.user)
        response = self.client.post(self.url, self.default_search_params)
        self.assertDictEqual(response.json(), dict(success=True))

        # Check that the images were deleted.
        self.assertRaises(
            Image.DoesNotExist, Image.objects.get, pk=self.img1.pk)
        self.assertRaises(
            Image.DoesNotExist, Image.objects.get, pk=self.img2.pk)
        self.assertRaises(
            Image.DoesNotExist, Image.objects.get, pk=self.img3.pk)

    def test_delete_by_aux_meta(self):
        """
        Delete images by aux. meta.
        """
        self.img1.metadata.aux1 = 'SiteA'
        self.img1.metadata.save()

        post_data = self.default_search_params.copy()
        post_data['aux1'] = 'SiteA'

        self.client.force_login(self.user)
        response = self.client.post(self.url, post_data)
        self.assertDictEqual(response.json(), dict(success=True))

        # Check that we can get image 2 and 3, but not 1,
        # which we chose to delete.
        self.assertRaises(
            Image.DoesNotExist, Image.objects.get, pk=self.img1.pk)
        Image.objects.get(pk=self.img2.pk)
        Image.objects.get(pk=self.img3.pk)

    def test_delete_by_image_ids(self):
        """
        Delete images of particular image ids.
        """
        post_data = dict(
            image_form_type='ids',
            ids=','.join([str(self.img1.pk), str(self.img3.pk)])
        )

        self.client.force_login(self.user)
        response = self.client.post(self.url, post_data)
        self.assertDictEqual(response.json(), dict(success=True))

        # Check that we can get image 2, but not 1 and 3,
        # which we chose to delete.
        self.assertRaises(
            Image.DoesNotExist, Image.objects.get, pk=self.img1.pk)
        Image.objects.get(pk=self.img2.pk)
        self.assertRaises(
            Image.DoesNotExist, Image.objects.get, pk=self.img3.pk)

    def test_delete_related_objects(self):
        """
        Delete not just the Image objects, but also related objects.
        """
        post_data = dict(
            image_form_type='ids',
            ids=','.join([str(self.img1.pk), str(self.img3.pk)])
        )
        metadata_1_pk = self.img1.metadata.pk
        metadata_2_pk = self.img2.metadata.pk
        metadata_3_pk = self.img3.metadata.pk
        status_1_pk = self.img1.status.pk
        status_2_pk = self.img2.status.pk
        status_3_pk = self.img3.status.pk

        self.client.force_login(self.user)
        response = self.client.post(self.url, post_data)
        self.assertDictEqual(response.json(), dict(success=True))

        self.assertRaises(
            Metadata.DoesNotExist, Metadata.objects.get, pk=metadata_1_pk)
        Metadata.objects.get(pk=metadata_2_pk)
        self.assertRaises(
            Metadata.DoesNotExist, Metadata.objects.get, pk=metadata_3_pk)

        self.assertRaises(
            ImageStatus.DoesNotExist, ImageStatus.objects.get, pk=status_1_pk)
        ImageStatus.objects.get(pk=status_2_pk)
        self.assertRaises(
            ImageStatus.DoesNotExist, ImageStatus.objects.get, pk=status_3_pk)

    def test_do_not_delete_images_of_other_sources(self):
        """
        Doesn't hurt to have a sanity check.
        """
        source2 = self.create_source(self.user)
        img21 = self.upload_image_new(self.user, source2)
        img22 = self.upload_image_new(self.user, source2)

        self.client.force_login(self.user)
        response = self.client.post(self.url, self.default_search_params)
        self.assertDictEqual(response.json(), dict(success=True))

        # Check that the second source's images were not deleted.
        Image.objects.get(pk=img21.pk)
        Image.objects.get(pk=img22.pk)


class ErrorTest(ClientTest):
    @classmethod
    def setUpTestData(cls):
        super(ErrorTest, cls).setUpTestData()

        cls.user = cls.create_user()
        cls.source = cls.create_source(cls.user)
        cls.img1 = cls.upload_image_new(cls.user, cls.source)
        cls.img2 = cls.upload_image_new(cls.user, cls.source)
        cls.img3 = cls.upload_image_new(cls.user, cls.source)

        cls.url = reverse('browse_delete_ajax', args=[cls.source.pk])

        cls.default_search_params = dict(
            image_form_type='search',
            aux1='', aux2='', aux3='', aux4='', aux5='',
            height_in_cm='', latitude='', longitude='', depth='',
            photographer='', framing='', balance='',
            date_filter_0='year', date_filter_1='',
            date_filter_2='', date_filter_3='',
            annotation_status='',
        )

    def test_no_search_form(self):
        self.client.force_login(self.user)
        response = self.client.post(self.url, dict())
        self.assertDictEqual(response.json(), dict(
            error=(
                "You must first use the search form"
                " or select images on the page to use the delete function."
            )
        ))
        # Since the images weren't deleted,
        # these image-getting statements should not raise errors.
        Image.objects.get(pk=self.img1.pk)
        Image.objects.get(pk=self.img2.pk)
        Image.objects.get(pk=self.img3.pk)

    def test_form_error(self):
        post_data = self.default_search_params.copy()
        # Nonexistent aux1 value in this source.
        post_data['annotation_status'] = 'invalid_value'

        self.client.force_login(self.user)
        response = self.client.post(self.url, post_data)
        self.assertDictEqual(response.json(), dict(
            error=(
                "There was an error with the form."
                " Nothing was deleted."
            )
        ))
        Image.objects.get(pk=self.img1.pk)
        Image.objects.get(pk=self.img2.pk)
        Image.objects.get(pk=self.img3.pk)
