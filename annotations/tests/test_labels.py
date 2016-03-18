from django.core.urlresolvers import reverse
from lib.test_utils import ClientTest, MediaTestComponent

class LabelListTest(ClientTest):
    """
    Test the label list page.
    """

    def test_load_page(self):
        """Load the page."""
        response = self.client.get(reverse('label_list'))
        self.assertStatusOK(response)