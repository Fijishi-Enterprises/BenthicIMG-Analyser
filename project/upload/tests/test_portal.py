from __future__ import unicode_literals

from django.urls import reverse

from lib.tests.utils import BasePermissionTest


class PermissionTest(BasePermissionTest):

    def test_portal(self):
        url = reverse('upload_portal', args=[self.source.pk])
        template = 'upload/upload_portal.html'

        self.source_to_private()
        self.assertPermissionLevel(url, self.SOURCE_EDIT, template=template)
        self.source_to_public()
        self.assertPermissionLevel(url, self.SOURCE_EDIT, template=template)
