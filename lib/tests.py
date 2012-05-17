# Tests for non-app-specific pages.
from django.core.urlresolvers import reverse
from lib.test_utils import ClientTest


class IndexTest(ClientTest):
    """
    Test the site index page.
    """
    def test_index(self):
        response = self.client.get(reverse('index'))
        self.assertStatusOK(response)