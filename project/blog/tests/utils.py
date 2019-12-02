from __future__ import unicode_literals

from bs4 import BeautifulSoup
from django.shortcuts import resolve_url

from ..models import Entry


class BlogTestMixin(object):

    # These lines just exist to prevent an 'Unresolved attribute reference' or
    # similar IDE warning. The base test classes should end up setting
    # these in setup methods.
    client = None
    superuser = None

    @classmethod
    def create_entry(cls, **kwargs):
        # Defaults
        data = dict(
            title="A title",
            content="Some content",
            is_published=True,
            author=cls.superuser,
            tags="",
            preview_content="",
            preview_image=None,
        )

        # Override defaults with any kwargs that are present
        data.update(**kwargs)
        # Save entry
        entry = Entry(**data)
        entry.save()

        return entry

    def view_entry_list(self, user=None):
        if user:
            self.client.force_login(user)
        else:
            self.client.logout()

        url = resolve_url('blog:entry_list')
        response = self.client.get(url)

        return response

    def view_entry(self, entry, user=None):
        if user:
            self.client.force_login(user)
        else:
            self.client.logout()

        url = resolve_url('blog:entry_detail', entry.slug)
        response = self.client.get(url)

        return response

    @staticmethod
    def get_entry_content_html(entry_detail_response):
        response_soup = BeautifulSoup(
            entry_detail_response.content, 'html.parser')
        content_div = response_soup.find(
            'div', class_='blog-entry-content')
        return ''.join(
            [str(child) for child in content_div.children])
