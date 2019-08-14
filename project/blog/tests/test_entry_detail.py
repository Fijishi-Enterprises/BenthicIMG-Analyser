from __future__ import unicode_literals
import time

from bs4 import BeautifulSoup
from django.shortcuts import resolve_url

from lib.test_utils import BasePermissionTest, ClientTest
from .utils import BlogTestMixin


class PermissionTest(BasePermissionTest, BlogTestMixin):

    @classmethod
    def setUpTestData(cls):
        super(PermissionTest, cls).setUpTestData()

        cls.public_entry = cls.create_entry(is_published=True)
        cls.draft = cls.create_entry(is_published=False)

    def test_published(self):
        """Everyone can access published entries:
        logged out, regular users, and superusers."""
        url = resolve_url('blog:entry_detail', self.public_entry.slug)
        self.assertPermissionGranted(url, None)
        self.assertPermissionGranted(url, self.user)
        self.assertPermissionGranted(url, self.superuser)

    def test_draft(self):
        """Only superusers can access drafts."""
        url = resolve_url('blog:entry_detail', self.draft.slug)
        self.assertNotFound(url, None)
        self.assertNotFound(url, self.user)
        self.assertPermissionGranted(url, self.superuser)


class MarkdownTest(ClientTest, BlogTestMixin):
    """
    Check that andablog's Markdown is working fine. Just looking at a few kinds
    of Markdown features without being super thorough.
    """
    def test_heading(self):
        content = "## A header"
        entry = self.create_entry(content=content)

        response = self.view_entry(entry)
        content_html = self.get_entry_content_html(response)
        self.assertHTMLEqual(str(content_html), '<h2>A header</h2>')

    def test_italics(self):
        content = "Here is some *italic text*"
        entry = self.create_entry(content=content)

        response = self.view_entry(entry)
        content_html = self.get_entry_content_html(response)
        self.assertHTMLEqual(
            str(content_html), '<p>Here is some <em>italic text</em></p>')

    def test_link(self):
        content = "Here is [a link](http://example.com)"
        entry = self.create_entry(content=content)

        response = self.view_entry(entry)
        content_html = self.get_entry_content_html(response)
        self.assertHTMLEqual(
            str(content_html),
            '<p>Here is <a href="http://example.com">a link</a></p>')

    def test_image(self):
        """Here we just test embedding an image via Markdown, but we don't
        test the Entry Images feature (i.e. uploading an image to be associated
        with the current entry)."""
        content = (
            "An image:"
            " ![Alt text goes here](/path/to/my_image.png)")
        entry = self.create_entry(content=content)

        response = self.view_entry(entry)
        content_html = self.get_entry_content_html(response)
        self.assertHTMLEqual(
            str(content_html),
            '<p>An image:'
            '<img alt="Alt text goes here" src="/path/to/my_image.png" />'
            '</p>')


class LinkTest(ClientTest, BlogTestMixin):
    """
    Check the links on the entry detail page.
    """
    @classmethod
    def setUpTestData(cls):
        super(LinkTest, cls).setUpTestData()

        list_url = resolve_url('blog:entry_list')
        cls.blog_home_link_expected_html = \
            '<a href="{list_url}">Blog home</a>'.format(list_url=list_url)

    @staticmethod
    def get_nav_html(response):
        response_soup = BeautifulSoup(response.content, 'html.parser')
        navigation_div = response_soup.find(
            'div', class_='blog-entry-navigation')
        # Get all the HTML between the <div> </div> tags as a string
        return ''.join(str(node) for node in navigation_div.contents)

    def test_with_no_other_entry(self):
        entry = self.create_entry()

        response = self.view_entry(entry)

        self.assertHTMLEqual(
            self.get_nav_html(response),
            self.blog_home_link_expected_html,
            "Navigation area only has the blog home link")

    def test_with_next_and_prev_entry_links(self):
        # Ordering is finicky if the test creates entries too quickly, so we
        # have to throttle it with sleep...
        # We create multiple earlier and later entries in order to test that
        # the NEXT earliest and NEXT latest entries are linked, not anything
        # beyond that.
        self.create_entry(title="Entry 1")
        time.sleep(0.01)
        entry_2 = self.create_entry(title="Entry 2")
        time.sleep(0.01)
        entry_3 = self.create_entry(title="Entry 3")
        time.sleep(0.01)
        entry_4 = self.create_entry(title="Entry 4")
        time.sleep(0.01)
        self.create_entry(title="Entry 5")

        response = self.view_entry(entry_3)

        url_2 = resolve_url('blog:entry_detail', entry_2.slug)
        url_4 = resolve_url('blog:entry_detail', entry_4.slug)
        next_link_expected_html = (
            '<a href="{url_4}" title="Entry 4">'
            ' &lt; Newer: Entry 4</a>'.format(url_4=url_4))
        prev_link_expected_html = (
            '<a href="{url_2}" title="Entry 2">'
            ' Older: Entry 2 &gt;</a>'.format(url_2=url_2))
        nav_expected_html = (
            next_link_expected_html
            + ' | ' + self.blog_home_link_expected_html
            + ' | ' + prev_link_expected_html)

        self.assertHTMLEqual(
            self.get_nav_html(response), nav_expected_html,
            "Navigation area has the expected next, home, and prev links")

    def test_with_next_only(self):
        entry_1 = self.create_entry(title="Entry 1")
        time.sleep(0.01)
        entry_2 = self.create_entry(title="Entry 2")

        response = self.view_entry(entry_1)

        url_2 = resolve_url('blog:entry_detail', entry_2.slug)
        next_link_expected_html = (
            '<a href="{url_2}" title="Entry 2">'
            ' &lt; Newer: Entry 2</a>'.format(url_2=url_2))
        nav_expected_html = (
            next_link_expected_html
            + ' | ' + self.blog_home_link_expected_html)

        self.assertHTMLEqual(
            self.get_nav_html(response), nav_expected_html,
            "Navigation area has the expected next and home links")

    def test_with_prev_only(self):
        entry_1 = self.create_entry(title="Entry 1")
        time.sleep(0.01)
        entry_2 = self.create_entry(title="Entry 2")

        response = self.view_entry(entry_2)

        url_1 = resolve_url('blog:entry_detail', entry_1.slug)
        prev_link_expected_html = (
            '<a href="{url_1}" title="Entry 1">'
            ' Older: Entry 1 &gt;</a>'.format(url_1=url_1))
        nav_expected_html = (
            self.blog_home_link_expected_html
            + ' | ' + prev_link_expected_html)

        self.assertHTMLEqual(
            self.get_nav_html(response), nav_expected_html,
            "Navigation area has the expected home and prev links")

    def test_viewing_draft(self):
        self.create_entry(title="Entry 1")
        time.sleep(0.01)
        entry_2 = self.create_entry(title="Entry 2")
        entry_draft = self.create_entry(title="Entry 3", is_published=False)

        # Need to be admin to view draft
        response = self.view_entry(entry_draft, self.superuser)

        url_2 = resolve_url('blog:entry_detail', entry_2.slug)
        prev_link_expected_html = (
            '<a href="{url_2}" title="Entry 2">'
            ' Older: Entry 2 &gt;</a>'.format(url_2=url_2))
        nav_expected_html = (
            self.blog_home_link_expected_html
            + ' | ' + prev_link_expected_html)

        self.assertHTMLEqual(
            self.get_nav_html(response), nav_expected_html,
            "From a draft, there should be a prev link to the"
            " latest published entry")

    def test_drafts_ignored_by_prev_next(self):
        entry_1 = self.create_entry(title="Entry 1")
        time.sleep(0.01)
        entry_2 = self.create_entry(title="Entry 2")
        self.create_entry(title="Entry 3", is_published=False)

        # Even admins shouldn't see drafts in prev/next (since it could be
        # confusing, making it look like the draft was a published entry)
        response = self.view_entry(entry_2, self.superuser)

        url_1 = resolve_url('blog:entry_detail', entry_1.slug)
        prev_link_expected_html = (
            '<a href="{url_1}" title="Entry 1">'
            ' Older: Entry 1 &gt;</a>'.format(url_1=url_1))
        nav_expected_html = (
            self.blog_home_link_expected_html
            + ' | ' + prev_link_expected_html)

        self.assertHTMLEqual(
            self.get_nav_html(response), nav_expected_html,
            "From a draft, there should be a prev link to the"
            " latest published entry")
