from __future__ import unicode_literals
import six

from django.shortcuts import resolve_url

from lib.tests.utils import ClientTest


class BaseExportTest(ClientTest):

    @classmethod
    def setUpTestData(cls):
        super(BaseExportTest, cls).setUpTestData()

        # Image search parameters
        cls.default_search_params = dict(
            image_form_type='search',
            aux1='', aux2='', aux3='', aux4='', aux5='',
            height_in_cm='', latitude='', longitude='', depth='',
            photographer='', framing='', balance='',
            date_filter_0='year', date_filter_1='',
            date_filter_2='', date_filter_3='',
            annotation_status='', image_name='',
        )

    def export_annotations(self, post_data):
        """POST to export_annotations, and return the response."""
        self.client.force_login(self.user)
        return self.client.post(
            resolve_url('export_annotations', self.source.pk), post_data)

    def export_image_covers(self, post_data):
        """POST to export_image_covers, and return the response."""
        self.client.force_login(self.user)
        return self.client.post(
            resolve_url('export_image_covers', self.source.pk), post_data)

    def export_metadata(self, post_data):
        """POST to export_metadata, and return the response."""
        self.client.force_login(self.user)
        return self.client.post(
            resolve_url('export_metadata', self.source.pk), post_data)

    def assert_csv_content_equal(self, actual_csv_content, expected_lines):
        """
        Tests that a CSV's content is as expected.

        :param actual_csv_content: CSV content from the export view's
          response, as either a Unicode string or a bytes-like object
          (bytes if passing response.content into here directly, Unicode if
          pre-processed first).
        :param expected_lines: List of strings, without newline characters,
          representing the expected line contents. Note that this is a
          different format from actual_csv_content, just because it's easier
          to type non-newline strings in Python code.
        Throws AssertionError if actual and expected CSVs are not equal.
        """
        # Convert from bytes to Unicode if necessary.
        if isinstance(actual_csv_content, six.binary_type):
            actual_csv_content = actual_csv_content.decode('utf-8')

        # The Python csv module uses \r\n by default (as part of the Excel
        # dialect). Due to the way we compare line by line, splitting on
        # \n would mess up the comparison, so we use split() instead of
        # splitlines().
        actual_lines = actual_csv_content.split('\r\n')
        # Since we're not using splitlines(), we have to deal with ending
        # newlines manually.
        if actual_lines[-1] == "":
            actual_lines.pop()
        expected_content = '\r\n'.join(expected_lines) + '\r\n'

        # Compare individual lines (so that if we get a mismatch, the error
        # message will be readable)
        for line_num, actual_line in enumerate(actual_lines, 1):
            expected_line = expected_lines[line_num-1]
            self.assertEqual(actual_line, expected_line, msg=(
                "Line {line_num} not equal | Actual: {actual_line}"
                " | Expected: {expected_line}").format(
                line_num=line_num, actual_line=actual_line,
                expected_line=expected_line,
            ))
        # Compare entire file (to ensure line separator types are correct too)
        self.assertEqual(actual_csv_content, expected_content)
