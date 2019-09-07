from __future__ import unicode_literals

from django.conf import settings
from django.contrib.flatpages.models import FlatPage
from django.contrib.sites.models import Site

from lib.test_utils import ClientTest


class FlatpagesTest(ClientTest):
    """
    Test flatpages.
    """
    @classmethod
    def setUpTestData(cls):
        super(FlatpagesTest, cls).setUpTestData()

    def test_new_flatpage(self):
        """Create a flatpage and view it at its URL."""
        page = FlatPage(
            url='/help/faq/', title="FAQ", content="FAQ contents go here.")
        page.save()
        page.sites.add(Site.objects.get(pk=settings.SITE_ID))
        page.save()

        response = self.client.get('/pages/help/faq/')
        self.assertTemplateUsed(response, 'flatpages/default.html')

    def test_404(self):
        """URL is in the flatpages directory, but the page name doesn't exist.
        Should 404."""
        response = self.client.get('/pages/nonexistent-page/')
        self.assertTemplateUsed(response, '404.html')
