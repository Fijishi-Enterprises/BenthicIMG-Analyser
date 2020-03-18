from __future__ import unicode_literals

from django.urls import reverse

from lib.tests.utils import BasePermissionTest


class BackendViewPermissions(BasePermissionTest):

    def test_backend_main(self):
        url = reverse('backend_main', args=[self.source.pk])
        template = 'vision_backend/backend_main.html'

        self.source_to_private()
        self.assertPermissionLevel(url, self.SOURCE_VIEW, template=template)
        self.source_to_public()
        self.assertPermissionLevel(url, self.SIGNED_OUT, template=template)

    def test_backend_overview(self):
        # Requires at least 1 image
        self.upload_image(self.user, self.source)

        url = reverse('backend_overview')
        template = 'vision_backend/overview.html'

        self.assertPermissionLevel(
            url, self.SUPERUSER, template=template,
            deny_type=self.REQUIRE_LOGIN)

    def test_cm_test(self):
        url = reverse('cm_test')
        template = 'vision_backend/cm_test.html'

        self.assertPermissionLevel(
            url, self.SUPERUSER, template=template,
            deny_type=self.REQUIRE_LOGIN)
