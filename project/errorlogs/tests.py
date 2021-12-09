from unittest import mock

from django.urls import reverse

from lib.tests.utils import ClientTest
from .models import ErrorLog


class ErrorLogTest(ClientTest):

    @staticmethod
    def mock_render(*args):
        raise ValueError("Test error")

    def test_get(self):
        # Mock render(), which is going to be called at the end of the view.
        # This is django.shortcuts.render, but due to the way it's imported
        # in views, the patch target is lib.views.render.
        with mock.patch('lib.views.render', self.mock_render):
            try:
                self.client.get(reverse('index'))
            except ValueError:
                # TODO: When we're on Django 3.0 or higher, use the
                # new Client option raise_request_exception to avoid bubbling
                # the request exception up to the test. That way we don't have
                # to catch the exception here.
                pass

        log = ErrorLog.objects.latest('pk')
        self.assertEqual(log.kind, "ValueError")
        self.assertEqual(log.info, "Test error")

        relative_url = reverse('index')
        self.assertEqual(log.path, f'http://testserver{relative_url}')
        self.assertTrue(
            log.data.startswith("Traceback (most recent call last):"))
        self.assertInHTML(f"<h1>ValueError at {relative_url}</h1>", log.html)

    def test_post(self):
        user = self.create_user()
        self.client.force_login(user)
        with mock.patch('images.views.render', self.mock_render):
            try:
                self.client.post(reverse('source_new'))
            except ValueError:
                # TODO: When we're on Django 3.0 or higher, use the
                # new Client option raise_request_exception to avoid bubbling
                # the request exception up to the test. That way we don't have
                # to catch the exception here.
                pass

        log = ErrorLog.objects.latest('pk')
        self.assertEqual(log.kind, "ValueError")
        self.assertEqual(log.info, "Test error")

        relative_url = reverse('source_new')
        self.assertEqual(log.path, f'http://testserver{relative_url}')
        self.assertTrue(
            log.data.startswith("Traceback (most recent call last):"))
        self.assertInHTML(f"<h1>ValueError at {relative_url}</h1>", log.html)
