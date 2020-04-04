from __future__ import unicode_literals
from django.urls import reverse

from images.models import Source
from lib.tests.utils import BasePermissionTest, ClientTest


class PermissionTest(BasePermissionTest):

    def test_invites_manage(self):
        url = reverse('invites_manage')
        template = 'images/invites_manage.html'

        self.assertPermissionLevel(
            url, self.SIGNED_IN, template=template,
            deny_type=self.REQUIRE_LOGIN)

    def test_source_admin(self):
        url = reverse('source_admin', args=[self.source.pk])
        template = 'images/source_invite.html'

        self.source_to_private()
        self.assertPermissionLevel(url, self.SOURCE_ADMIN, template=template)
        self.source_to_public()
        self.assertPermissionLevel(url, self.SOURCE_ADMIN, template=template)


class SourceInviteTest(ClientTest):
    """
    Test sending and accepting invites to sources.
    """
    @classmethod
    def setUpTestData(cls):
        super(SourceInviteTest, cls).setUpTestData()

        cls.user_creator = cls.create_user()
        cls.source = cls.create_source(cls.user_creator)

        cls.user_editor = cls.create_user()

    def test_source_invite(self):
        # Send invite as source admin
        self.client.force_login(self.user_creator)
        self.client.post(
            reverse('source_admin', kwargs={'source_id': self.source.pk}),
            dict(
                sendInvite='sendInvite',
                recipient=self.user_editor.username,
                source_perm=Source.PermTypes.EDIT.code,
            ),
        )

        # Accept invite as prospective source member
        self.client.force_login(self.user_editor)
        self.client.post(
            reverse('invites_manage'),
            dict(
                accept='',
                sender=self.user_creator.pk,
                source=self.source.pk,
            ),
        )

        # Test that the given permission level works
        self.client.force_login(self.user_editor)
        response = self.client.get(
            reverse('upload_images', kwargs={'source_id': self.source.pk}))
        self.assertTemplateUsed(response, 'upload/upload_images.html')


# TODO: Test other source_admin functions
