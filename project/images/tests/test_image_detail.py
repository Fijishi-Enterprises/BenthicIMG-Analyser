# Test image_detail and image_detail_edit views.

from __future__ import unicode_literals
from django.urls import reverse

from lib.tests.utils import BasePermissionTest, ClientTest


class PermissionTest(BasePermissionTest):

    def test_image_detail_private_source(self):
        img = self.upload_image(self.user, self.private_source)
        url = reverse('image_detail', args=[img.id])
        self.assertPermissionDenied(url, None)
        self.assertPermissionDenied(url, self.user_outsider)
        self.assertPermissionGranted(url, self.user_viewer)
        self.assertPermissionGranted(url, self.user_editor)
        self.assertPermissionGranted(url, self.user_admin)

    def test_image_detail_public_source(self):
        img = self.upload_image(self.user, self.public_source)
        url = reverse('image_detail', args=[img.id])
        self.assertPermissionGranted(url, None)
        self.assertPermissionGranted(url, self.user_outsider)
        self.assertPermissionGranted(url, self.user_viewer)
        self.assertPermissionGranted(url, self.user_editor)
        self.assertPermissionGranted(url, self.user_admin)

    def test_image_detail_edit_private_source(self):
        img = self.upload_image(self.user, self.private_source)
        url = reverse('image_detail_edit', args=[img.id])
        self.assertPermissionDenied(url, None)
        self.assertPermissionDenied(url, self.user_outsider)
        self.assertPermissionDenied(url, self.user_viewer)
        self.assertPermissionGranted(url, self.user_editor)
        self.assertPermissionGranted(url, self.user_admin)

    def test_image_detail_edit_public_source(self):
        img = self.upload_image(self.user, self.public_source)
        url = reverse('image_detail_edit', args=[img.id])
        self.assertPermissionDenied(url, None)
        self.assertPermissionDenied(url, self.user_outsider)
        self.assertPermissionDenied(url, self.user_viewer)
        self.assertPermissionGranted(url, self.user_editor)
        self.assertPermissionGranted(url, self.user_admin)


class ImageDetailTest(ClientTest):
    """
    Test the image view/detail page.
    """
    @classmethod
    def setUpTestData(cls):
        super(ImageDetailTest, cls).setUpTestData()

        cls.user = cls.create_user()

        # Create a source
        cls.source = cls.create_source(cls.user)

        # Upload a small image and a large image
        cls.small_image = cls.upload_image(
            cls.user, cls.source, image_options=dict(width=400, height=400))
        cls.large_image = cls.upload_image(
            cls.user, cls.source, image_options=dict(width=1600, height=1600))

    def test_page_with_small_image(self):
        url = reverse('image_detail', kwargs={'image_id': self.small_image.id})
        response = self.client.get(url)
        self.assertStatusOK(response)

        # Try fetching the page a second time, to make sure thumbnail
        # generation doesn't go nuts.
        response = self.client.get(url)
        self.assertStatusOK(response)

    def test_page_with_large_image(self):
        url = reverse('image_detail', kwargs={'image_id': self.large_image.id})
        response = self.client.get(url)
        self.assertStatusOK(response)

        # Try fetching the page a second time, to make sure thumbnail
        # generation doesn't go nuts.
        response = self.client.get(url)
        self.assertStatusOK(response)
