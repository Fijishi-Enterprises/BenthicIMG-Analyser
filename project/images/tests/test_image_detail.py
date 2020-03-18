# Test image_detail and image_detail_edit views.

from __future__ import unicode_literals
from django.urls import reverse

from lib.tests.utils import BasePermissionTest, ClientTest


class PermissionTest(BasePermissionTest):

    @classmethod
    def setUpTestData(cls):
        super(PermissionTest, cls).setUpTestData()

        cls.img = cls.upload_image(cls.user, cls.source)

    def test_image_detail(self):
        url = reverse('image_detail', args=[self.img.id])
        template = 'images/image_detail.html'

        self.source_to_private()
        self.assertPermissionLevel(url, self.SOURCE_VIEW, template=template)
        self.source_to_public()
        self.assertPermissionLevel(url, self.SIGNED_OUT, template=template)

    def test_image_detail_edit(self):
        url = reverse('image_detail_edit', args=[self.img.id])
        template = 'images/image_detail_edit.html'

        self.source_to_private()
        self.assertPermissionLevel(url, self.SOURCE_EDIT, template=template)
        self.source_to_public()
        self.assertPermissionLevel(url, self.SOURCE_EDIT, template=template)


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


# TODO: Test image detail edit.
