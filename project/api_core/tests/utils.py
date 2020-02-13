from __future__ import unicode_literals

from django.core.cache import cache
from django.urls import reverse
from rest_framework import status

from images.models import Source
from lib.tests.utils import ClientTest


class BaseAPITest(ClientTest):

    longMessage = True

    def setUp(self):
        super(BaseAPITest, self).setUp()

        # DRF implements throttling by tracking usage counts in the cache.
        # We don't want usages in one test to trigger throttling in another
        # test. So we clear the cache between tests.
        cache.clear()

    @classmethod
    def setUpTestData(cls):
        super(BaseAPITest, cls).setUpTestData()

        # Don't want DRF throttling to be a factor during class setup, either.
        cache.clear()

    def assertNeedsAuth(self, url, msg="Should get 403"):
        # Request with no token header
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN, msg)

        self.assertDictEqual(
            response.json(),
            dict(errors=[
                dict(detail="Authentication credentials were not provided.")]),
            "Error response's body should be as expected")

    def assertMethodNotAllowedResponse(self, response, msg="Should get 405"):
        self.assertEqual(
            response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED, msg)

        response_json = response.json()
        self.assertIn(
            'errors', response_json,
            "Response should have top-level member 'errors'")
        error_detail = response_json['errors'][0]['detail']
        self.assertTrue(
            error_detail.startswith("Method ")
            and error_detail.endswith(" not allowed."),
            "Response error detail should be as expected")

    def assertThrottleResponse(self, response, msg="Should get 429"):
        self.assertEqual(
            response.status_code, status.HTTP_429_TOO_MANY_REQUESTS, msg)

        response_json = response.json()
        self.assertIn(
            'errors', response_json,
            "Response should have top-level member 'errors'")
        self.assertTrue(
            response_json['errors'][0]['detail'].startswith(
                "Request was throttled. Expected available in "),
            "Response error detail should be as expected")


class BaseAPIPermissionTest(BaseAPITest):
    """
    Test view permissions.

    To generalize this class to test any view, we might want to add some
    flexibility on what is created with each source (or just create the minimum
    and leave further customization to subclasses).
    """
    @classmethod
    def get_token_headers(cls, username, password):
        # Don't want DRF throttling to be a factor here, either.
        cache.clear()

        response = cls.client.post(
            reverse('api:token_auth'),
            dict(
                username=username,
                password=password,
            ),
        )
        token = response.json()['token']
        return dict(
            HTTP_AUTHORIZATION='Token {token}'.format(token=token))

    @classmethod
    def setUpTestData(cls):
        super(BaseAPIPermissionTest, cls).setUpTestData()

        cls.user = cls.create_user(username='user', password='SamplePass')
        cls.user_token_headers = cls.get_token_headers('user', 'SamplePass')

        labels = cls.create_labels(cls.user, ['A', 'B'], 'GroupA')

        cls.public_source = cls.create_source(
            cls.user, visibility=Source.VisibilityTypes.PUBLIC)
        cls.create_labelset(cls.user, cls.public_source, labels)

        cls.private_source = cls.create_source(
            cls.user, visibility=Source.VisibilityTypes.PRIVATE)
        cls.create_labelset(cls.user, cls.private_source, labels)

        # Not a source member
        cls.user_outsider = cls.create_user(
            username='user_outsider', password='SamplePass')
        cls.user_outsider_token_headers = cls.get_token_headers(
            'user_outsider', 'SamplePass')

        # View permissions
        cls.user_viewer = cls.create_user(
            username='user_viewer', password='SamplePass')
        cls.user_viewer_token_headers = cls.get_token_headers(
            'user_viewer', 'SamplePass')
        cls.add_source_member(
            cls.user, cls.public_source,
            cls.user_viewer, Source.PermTypes.VIEW.code)
        cls.add_source_member(
            cls.user, cls.private_source,
            cls.user_viewer, Source.PermTypes.VIEW.code)

        # Edit permissions
        cls.user_editor = cls.create_user(
            username='user_editor', password='SamplePass')
        cls.user_editor_token_headers = cls.get_token_headers(
            'user_editor', 'SamplePass')
        cls.add_source_member(
            cls.user, cls.public_source,
            cls.user_editor, Source.PermTypes.EDIT.code)
        cls.add_source_member(
            cls.user, cls.private_source,
            cls.user_editor, Source.PermTypes.EDIT.code)

        # Admin permissions
        cls.user_admin = cls.create_user(
            username='user_admin', password='SamplePass')
        cls.user_admin_token_headers = cls.get_token_headers(
            'user_admin', 'SamplePass')
        cls.add_source_member(
            cls.user, cls.public_source,
            cls.user_admin, Source.PermTypes.ADMIN.code)
        cls.add_source_member(
            cls.user, cls.private_source,
            cls.user_admin, Source.PermTypes.ADMIN.code)
