# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.urls import reverse

from lib.tests.utils import BasePermissionTest


class PermissionTest(BasePermissionTest):

    def test_media_ajax(self):
        url = reverse('async_media:media_ajax')

        self.assertPermissionLevel(
            url, self.SIGNED_OUT, is_json=True, post_data={})

    def test_media_poll_ajax(self):
        url = reverse('async_media:media_poll_ajax')

        self.assertPermissionLevel(
            url, self.SIGNED_OUT, is_json=True, post_data={})
