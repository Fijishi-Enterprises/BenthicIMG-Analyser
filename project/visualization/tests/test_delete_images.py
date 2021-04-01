from django.urls import reverse

from images.models import Image, Metadata
from vision_backend.models import Features
from lib.tests.utils import BasePermissionTest, ClientTest


class PermissionTest(BasePermissionTest):
    """
    Test page permissions.
    """
    def test_browse_delete_ajax(self):
        url = reverse('browse_delete_ajax', args=[self.source.pk])

        self.source_to_private()
        self.assertPermissionLevel(
            url, self.SOURCE_EDIT, is_json=True, post_data={})
        self.source_to_public()
        self.assertPermissionLevel(
            url, self.SOURCE_EDIT, is_json=True, post_data={})


class SuccessTest(ClientTest):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()

        cls.user = cls.create_user()
        cls.source = cls.create_source(cls.user)
        cls.img1 = cls.upload_image(cls.user, cls.source)
        cls.img2 = cls.upload_image(cls.user, cls.source)
        cls.img3 = cls.upload_image(cls.user, cls.source)

        cls.url = reverse('browse_delete_ajax', args=[cls.source.pk])

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
            sort_method='name', sort_direction='asc',
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
        features_1_pk = self.img1.features.pk
        features_2_pk = self.img2.features.pk
        features_3_pk = self.img3.features.pk

        self.client.force_login(self.user)
        response = self.client.post(self.url, post_data)
        self.assertDictEqual(response.json(), dict(success=True))

        self.assertRaises(
            Metadata.DoesNotExist, Metadata.objects.get, pk=metadata_1_pk)
        Metadata.objects.get(pk=metadata_2_pk)
        self.assertRaises(
            Metadata.DoesNotExist, Metadata.objects.get, pk=metadata_3_pk)    

        self.assertRaises(Features.DoesNotExist, Features.objects.get, pk=features_1_pk)
        Features.objects.get(pk=features_2_pk)
        self.assertRaises(Features.DoesNotExist, Features.objects.get, pk=features_3_pk)


class OtherSourceTest(ClientTest):
    """
    Ensure that the UI doesn't allow deleting other sources' images.
    """
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()

        cls.user = cls.create_user()
        cls.source = cls.create_source(cls.user)
        cls.img1 = cls.upload_image(cls.user, cls.source)
        cls.img2 = cls.upload_image(cls.user, cls.source)
        source2 = cls.create_source(cls.user)
        cls.img21 = cls.upload_image(cls.user, source2)
        cls.img22 = cls.upload_image(cls.user, source2)

        cls.url = reverse('browse_delete_ajax', args=[cls.source.pk])

    def test_dont_delete_other_sources_images_via_search_form(self):
        """
        Sanity check that the search form only picks up images in the current
        source.
        """
        search_params = dict(
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
            sort_method='name', sort_direction='asc',
        )
        self.client.force_login(self.user)
        response = self.client.post(self.url, search_params)
        self.assertDictEqual(response.json(), dict(success=True))

        # Source 1's images deleted
        self.assertRaises(
            Image.DoesNotExist, Image.objects.get, pk=self.img1.pk)
        self.assertRaises(
            Image.DoesNotExist, Image.objects.get, pk=self.img2.pk)

        # Source 2's images not deleted
        Image.objects.get(pk=self.img21.pk)
        Image.objects.get(pk=self.img22.pk)

    def test_dont_delete_other_sources_images_via_ids(self):
        """
        Sanity check that specifying by IDs only accepts images in the current
        source.
        """
        post_data = dict(
            image_form_type='ids',
            ids=','.join([str(self.img1.pk), str(self.img22.pk)])
        )

        self.client.force_login(self.user)
        response = self.client.post(self.url, post_data)
        self.assertDictEqual(response.json(), dict(success=True))

        # Check that we can get image 22, but not 1.
        self.assertRaises(
            Image.DoesNotExist, Image.objects.get, pk=self.img1.pk)
        Image.objects.get(pk=self.img22.pk)


class ErrorTest(ClientTest):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()

        cls.user = cls.create_user()
        cls.source = cls.create_source(cls.user)
        cls.img1 = cls.upload_image(cls.user, cls.source)
        cls.img2 = cls.upload_image(cls.user, cls.source)
        cls.img3 = cls.upload_image(cls.user, cls.source)

        cls.url = reverse('browse_delete_ajax', args=[cls.source.pk])

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
            sort_method='name', sort_direction='asc',
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
