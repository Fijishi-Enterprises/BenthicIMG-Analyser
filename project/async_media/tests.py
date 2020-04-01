# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from bs4 import BeautifulSoup
from django.core.cache import cache
from django.urls import reverse
from easy_thumbnails.files import get_thumbnailer

from lib.tests.utils import BasePermissionTest, ClientTest


class PermissionTest(BasePermissionTest):

    def test_media_ajax(self):
        url = reverse('async_media:media_ajax')

        self.assertPermissionLevel(
            url, self.SIGNED_OUT, is_json=True, post_data={})

    def test_media_poll_ajax(self):
        url = reverse('async_media:media_poll_ajax')

        self.assertPermissionLevel(
            url, self.SIGNED_OUT, is_json=True, post_data={})


class BrowseImagesThumbnailsTest(ClientTest):
    """
    Test the thumbnail functionality in Browse Images.
    """
    @classmethod
    def setUpTestData(cls):
        super(BrowseImagesThumbnailsTest, cls).setUpTestData()

        cls.user = cls.create_user()
        cls.source = cls.create_source(cls.user)
        cls.browse_url = reverse('browse_images', args=[cls.source.pk])

    def setUp(self):
        super(BrowseImagesThumbnailsTest, self).setUp()

        # Async media uses the cache to store media generation requests.
        # Probably best to ensure subsequent tests can't interfere with
        # each other.
        cache.clear()

    def test_load_existing_thumbnail(self):
        img = self.upload_image(self.user, self.source)

        # Generate thumbnail before loading browse page
        thumbnail = get_thumbnailer(img.original_file).get_thumbnail(
            dict(size=(150, 150)), generate=True)

        # Load browse page
        response = self.client.get(self.browse_url)
        response_soup = BeautifulSoup(response.content, 'html.parser')
        thumb_image = response_soup.find('img', class_='thumb')

        self.assertEqual(
            thumbnail.url, thumb_image.attrs.get('src'),
            msg="Existing thumbnail should be loaded on the browse page")

    def test_generate_and_retrieve_thumbnail(self):
        img = self.upload_image(self.user, self.source)

        # Load browse page
        response = self.client.get(self.browse_url)
        response_soup = BeautifulSoup(response.content, 'html.parser')
        thumb_image = response_soup.find('img', class_='thumb')
        request_hash = thumb_image.attrs.get('data-async-request-hash')

        # Generate thumbnail from browse page's hash (this is usually
        # initiated via Javascript).
        data = {'hashes[]': [request_hash]}
        self.client.post(reverse('async_media:media_ajax'), data=data)

        # Retrieve generated thumbnail
        data = dict(first_hash=request_hash)
        response = self.client.post(
            reverse('async_media:media_poll_ajax'), data=data)

        # Directly get thumbnail URL for assertion purposes
        thumbnail = get_thumbnailer(img.original_file).get_thumbnail(
            dict(size=(150, 150)), generate=False)

        self.assertDictEqual(
            response.json(),
            dict(
                media=[dict(index=0, url=thumbnail.url)],
                mediaRemaining=False),
            msg="Thumbnail should have been retrieved via async-media request")
