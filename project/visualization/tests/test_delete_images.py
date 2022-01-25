from django.urls import reverse

from images.models import Image, Metadata
from vision_backend.models import Features
from lib.tests.utils import BasePermissionTest, ClientTest


class PermissionTest(BasePermissionTest):
    """
    Test view permissions.
    """
    def test_browse_delete_ajax(self):
        url = reverse('browse_delete_ajax', args=[self.source.id])

        self.source_to_private()
        self.assertPermissionLevel(
            url, self.SOURCE_EDIT, is_json=True, post_data={})
        self.source_to_public()
        self.assertPermissionLevel(
            url, self.SOURCE_EDIT, is_json=True, post_data={})


class BaseDeleteTest(ClientTest):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()

        cls.user = cls.create_user()
        cls.source = cls.create_source(cls.user)

        cls.url = reverse('browse_delete_ajax', args=[cls.source.id])

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

    def assert_image_deleted(self, image_id, name):
        msg = f"Image {name} should be deleted"
        with self.assertRaises(Image.DoesNotExist, msg=msg):
            Image.objects.get(id=image_id)

    def assert_image_not_deleted(self, image_id, name):
        try:
            Image.objects.get(id=image_id)
        except Image.DoesNotExist:
            raise AssertionError(f"Image {name} should not be deleted")

    def assert_confirmation_message(self, count):
        """
        Call this after a successful deletion to check the top-of-page
        confirmation message.
        """
        browse_url = reverse('browse_images', args=[self.source.id])
        self.client.force_login(self.user)
        response = self.client.get(browse_url)
        self.assertContains(
            response,
            f"The {count} selected images have been deleted.")


class SuccessTest(BaseDeleteTest):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()

        cls.img1 = cls.upload_image(cls.user, cls.source)
        cls.img2 = cls.upload_image(cls.user, cls.source)
        cls.img3 = cls.upload_image(cls.user, cls.source)

    def test_delete_all_images(self):
        """
        Delete all images in the source.
        """
        self.client.force_login(self.user)
        response = self.client.post(self.url, self.default_search_params)
        self.assertDictEqual(response.json(), dict(success=True))

        self.assert_image_deleted(self.img1.id, "img1")
        self.assert_image_deleted(self.img2.id, "img2")
        self.assert_image_deleted(self.img3.id, "img3")

        self.assert_confirmation_message(count=3)

    def test_delete_by_aux_meta(self):
        """
        Delete when filtering images by auxiliary metadata.
        """
        self.img1.metadata.aux1 = 'SiteA'
        self.img1.metadata.save()

        post_data = self.default_search_params.copy()
        post_data['aux1'] = 'SiteA'

        self.client.force_login(self.user)
        response = self.client.post(self.url, post_data)
        self.assertDictEqual(response.json(), dict(success=True))

        self.assert_image_deleted(self.img1.id, "img1")
        self.assert_image_not_deleted(self.img2.id, "img2")
        self.assert_image_not_deleted(self.img3.id, "img3")

        self.assert_confirmation_message(count=1)

    def test_delete_by_image_ids(self):
        """
        Delete images of particular image ids.
        """
        post_data = dict(
            image_form_type='ids',
            ids=','.join([str(self.img1.id), str(self.img3.id)])
        )

        self.client.force_login(self.user)
        response = self.client.post(self.url, post_data)
        self.assertDictEqual(response.json(), dict(success=True))

        self.assert_image_deleted(self.img1.id, "img1")
        self.assert_image_not_deleted(self.img2.id, "img2")
        self.assert_image_deleted(self.img3.id, "img3")

        self.assert_confirmation_message(count=2)

    def test_delete_related_objects(self):
        """
        Delete not just the Image objects, but also related objects.
        """
        post_data = dict(
            image_form_type='ids',
            ids=','.join([str(self.img1.id), str(self.img3.id)])
        )
        metadata_1_id = self.img1.metadata.id
        metadata_2_id = self.img2.metadata.id
        metadata_3_id = self.img3.metadata.id
        features_1_id = self.img1.features.id
        features_2_id = self.img2.features.id
        features_3_id = self.img3.features.id

        self.client.force_login(self.user)
        response = self.client.post(self.url, post_data)
        self.assertDictEqual(response.json(), dict(success=True))

        with self.assertRaises(Metadata.DoesNotExist, msg="Should delete"):
            Metadata.objects.get(id=metadata_1_id)
        try:
            Metadata.objects.get(id=metadata_2_id)
        except Metadata.DoesNotExist:
            raise AssertionError("Should not delete")
        with self.assertRaises(Metadata.DoesNotExist, msg="Should delete"):
            Metadata.objects.get(id=metadata_3_id)

        with self.assertRaises(Features.DoesNotExist, msg="Should delete"):
            Features.objects.get(id=features_1_id)
        try:
            Features.objects.get(id=features_2_id)
        except Features.DoesNotExist:
            raise AssertionError("Should not delete")
        with self.assertRaises(Features.DoesNotExist, msg="Should delete"):
            Features.objects.get(id=features_3_id)


class OtherSourceTest(BaseDeleteTest):
    """
    Ensure that the UI doesn't allow deleting other sources' images.
    """
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()

        cls.img1 = cls.upload_image(cls.user, cls.source)
        cls.img2 = cls.upload_image(cls.user, cls.source)
        source2 = cls.create_source(cls.user)
        cls.img21 = cls.upload_image(cls.user, source2)
        cls.img22 = cls.upload_image(cls.user, source2)

    def test_dont_delete_other_sources_images_via_search_form(self):
        """
        Sanity check that the search form only picks up images in the current
        source.
        """
        self.client.force_login(self.user)
        response = self.client.post(self.url, self.default_search_params)
        self.assertDictEqual(response.json(), dict(success=True))

        self.assert_image_deleted(self.img1.id, "img1")
        self.assert_image_deleted(self.img2.id, "img2")

        self.assert_image_not_deleted(self.img21.id, "img21")
        self.assert_image_not_deleted(self.img22.id, "img22")

    def test_dont_delete_other_sources_images_via_ids(self):
        """
        Sanity check that specifying by IDs only accepts images in the current
        source.
        """
        post_data = dict(
            image_form_type='ids',
            ids=','.join([str(self.img1.id), str(self.img22.id)])
        )

        self.client.force_login(self.user)
        response = self.client.post(self.url, post_data)
        self.assertDictEqual(response.json(), dict(success=True))

        self.assert_image_deleted(self.img1.id, "img1")
        self.assert_image_not_deleted(self.img22.id, "img22")


class ErrorTest(BaseDeleteTest):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()

        cls.img1 = cls.upload_image(cls.user, cls.source)
        cls.img2 = cls.upload_image(cls.user, cls.source)
        cls.img3 = cls.upload_image(cls.user, cls.source)

    def test_no_search_form(self):
        self.client.force_login(self.user)
        response = self.client.post(self.url, dict())
        self.assertDictEqual(response.json(), dict(
            error=(
                "You must first use the search form or select images on the"
                " page to use the delete function. If you really want to"
                " delete all images, first click 'Search' without"
                " changing any of the search fields."
            )
        ))

        self.assert_image_not_deleted(self.img1.id, "img1")
        self.assert_image_not_deleted(self.img2.id, "img2")
        self.assert_image_not_deleted(self.img3.id, "img3")

    def test_form_error(self):
        post_data = self.default_search_params.copy()
        post_data['annotation_status'] = 'invalid_value'

        self.client.force_login(self.user)
        response = self.client.post(self.url, post_data)
        self.assertDictEqual(response.json(), dict(
            error=(
                "There was an error with the form."
                " Nothing was deleted."
            )
        ))

        self.assert_image_not_deleted(self.img1.id, "img1")
        self.assert_image_not_deleted(self.img2.id, "img2")
        self.assert_image_not_deleted(self.img3.id, "img3")
