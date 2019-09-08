from __future__ import unicode_literals
import re

from bs4 import BeautifulSoup
from django.conf import settings
from django.contrib.flatpages.models import FlatPage
from django.contrib.sites.models import Site
from django.urls import reverse

from lib.test_utils import ClientTest, sample_image_as_file


class FlatpagesTest(ClientTest):
    """
    Test flatpages in general.
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

    def test_markdown_to_html(self):
        """Markdown in the content field should be rendered as HTML when
        displaying the flatpage."""
        page = FlatPage(
            url='/help/faq/', title="FAQ",
            content="**FAQ contents** go *here.*")
        page.save()
        page.sites.add(Site.objects.get(pk=settings.SITE_ID))
        page.save()

        response = self.client.get('/pages/help/faq/')
        response_soup = BeautifulSoup(response.content, 'html.parser')
        container_soup = response_soup.find(
            'div', dict(id='content-container'))

        self.assertHTMLEqual(
            str(container_soup),
            '<div id="content-container">'
            '<p><strong>FAQ contents</strong> go <em>here.</em></p>'
            '</div>')


class FlatpageEditTest(ClientTest):
    """
    Test aspects of editing flatpages.
    """
    def test_flatpage_editor_has_markdownx_widget(self):
        self.client.force_login(self.superuser)
        response = self.client.get('/admin/flatpages/flatpage/add/')
        self.assertContains(
            response, 'class="markdownx-preview"',
            msg_prefix="markdownx preview element should be present")

    def test_markdownx_image_upload(self):
        """Simple check that the image upload view works."""
        data = dict(image=sample_image_as_file('sample.png'))
        response = self.client.post(
            reverse('markdownx_upload'), data,
            # The view's response type varies depending on what
            # request.is_ajax() returns. This ensures it returns True.
            HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        image_code = response.json()['image_code']

        image_code_regex = re.compile(
            # ![](
            r'!\[\]\('
            # One or more of anything except )
            r'([^)]+)'
            # )
            r'\)'
        )
        self.assertRegexpMatches(
            image_code, image_code_regex,
            "markdownx should return a valid image code")
