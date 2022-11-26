from typing import List
from unittest.case import TestCase

from django.core import mail

from ..models import ErrorLog


class ErrorReportTestMixin(TestCase):

    def assert_no_email(self):
        """
        It's trickier to implement a 'assert no error email' assertion method.
        Instead we'll have this less general but simpler one: no email
        at all. This is still useful for many error-related tests.
        """
        self.assertEqual(
            len(mail.outbox), 0, "Should have not sent an email")

    def assert_error_email(self, subject: str, body_contents: List[str]):
        self.assertGreaterEqual(
            len(mail.outbox), 1, "Should have at least one email")

        # Assume the latest email is the error email.
        error_email = mail.outbox[-1]
        self.assertEqual(
            f"[CoralNet] {subject}",
            error_email.subject,
            "Error email should have the expected subject")
        for body_content in body_contents:
            self.assertIn(
                body_content,
                error_email.body,
                "Email body should have the expected content")

    def assert_no_error_log_saved(self):
        self.assertFalse(
            ErrorLog.objects.exists(), "Should not have created error log")

    def assert_error_log_saved(self, kind, info):
        try:
            # Assume the latest error log is the one to check.
            error_log = ErrorLog.objects.latest('pk')
        except ErrorLog.DoesNotExist:
            raise AssertionError("Should have created error log")

        self.assertEqual(
            kind,
            error_log.kind,
            "Error log should have the expected class name")
        self.assertEqual(
            info,
            error_log.info,
            "Error log should have the expected error info")
