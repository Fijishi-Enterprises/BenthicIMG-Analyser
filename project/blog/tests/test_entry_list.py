from __future__ import unicode_literals
import time

from bs4 import BeautifulSoup
from django.shortcuts import resolve_url

from lib.tests.utils import BasePermissionTest, ClientTest
from .utils import BlogTestMixin


class PermissionTest(BasePermissionTest):

    def test_entry_list_permission(self):
        """Everyone can access the entry list."""
        url = resolve_url('blog:entry_list')
        template = 'blog/entry_list.html'

        self.assertPermissionLevel(
            url, self.SIGNED_OUT, template=template)


class FooterLinkTest(ClientTest):
    """This isn't exactly a test of the blog, but of the site footer that's on
    every page. This still seemed like an OK place to put the test though."""

    def test_footer_link_to_entry_list(self):
        index_response = self.client.get(resolve_url('index'))
        response_soup = BeautifulSoup(index_response.content, 'html.parser')
        footer_div = response_soup.find('div', id='footer')

        entry_list_link = footer_div.find(
            'a', href=resolve_url('blog:entry_list'))
        self.assertIsNotNone(
            entry_list_link, "Footer has a link to the entry list")


class EntryPreviewTest(ClientTest, BlogTestMixin):

    def test_auto_preview_of_short_entry(self):
        # Short entry (<= 26 words)
        self.create_entry(content="01 02 03 04 05 06 07 08 09 10")

        list_response = self.view_entry_list()
        response_soup = BeautifulSoup(list_response.content, 'html.parser')
        preview_div = response_soup.find(
            'div', class_='blog-entry-content-preview')
        preview_paragraph = preview_div.find('p')
        self.assertHTMLEqual(
            str(preview_paragraph),
            '<p>01 02 03 04 05 06 07 08 09 10</p>',
            "Entry preview consists of the entire entry")

    def test_auto_preview_of_long_entry(self):
        # Longer entry (> 26 words)
        self.create_entry(content=(
            "01 02 03 04 05 06 07 08 09 10 11 12 13 14 15"
            " 16 17 18 19 20 21 22 23 24 25 26 27 28 29 30"))

        list_response = self.view_entry_list()
        response_soup = BeautifulSoup(list_response.content, 'html.parser')
        preview_div = response_soup.find(
            'div', class_='blog-entry-content-preview')
        preview_paragraph = preview_div.find('p')
        self.assertHTMLEqual(
            str(preview_paragraph),
            '<p>01 02 03 04 05 06 07 08 09 10 11 12 13 14 15'
            ' 16 17 18 19 20 21 22 23 24 25 26 ...</p>',
            "Entry preview consists of the first X words and an ellipsis")

    def test_custom_preview(self):
        self.create_entry(
            content="01 02 03 04 05", preview_content="10 20 30 40 50")

        list_response = self.view_entry_list()
        response_soup = BeautifulSoup(list_response.content, 'html.parser')
        preview_div = response_soup.find(
            'div', class_='blog-entry-content-preview')
        preview_paragraph = preview_div.find('p')
        self.assertHTMLEqual(
            str(preview_paragraph),
            '<p>10 20 30 40 50</p>',
            "Entry preview consists of the specified preview content instead"
            " of the entry content itself")

    def test_links_to_entry_detail(self):
        entry = self.create_entry(title="A title")
        entry_url = resolve_url('blog:entry_detail', entry.slug)

        list_response = self.view_entry_list()
        response_soup = BeautifulSoup(list_response.content, 'html.parser')

        row_div = response_soup.find('div', class_='blog-entry-row')
        title_link = row_div.find('h3').find('a')
        self.assertHTMLEqual(
            str(title_link),
            '<a href="{url}">A title</a>'.format(url=entry_url),
            "Title link is as expected")

        preview_div = response_soup.find(
            'div', class_='blog-entry-content-preview')
        more_link = preview_div.find('a')
        self.assertHTMLEqual(
            str(more_link),
            '<a href="{url}">(More...)</a>'.format(url=entry_url),
            "More... link is as expected")


class ListedEntriesTest(ClientTest, BlogTestMixin):
    """
    Test that the expected entries are listed.
    """
    def test_drafts_only_viewable_by_admins(self):
        regular_user = self.create_user()
        self.create_entry(is_published=False)

        list_response = self.view_entry_list(user=regular_user)
        response_soup = BeautifulSoup(list_response.content, 'html.parser')
        row_div = response_soup.find('div', class_='blog-entry-row')
        self.assertIsNone(row_div, "A regular user can't see the draft")

        list_response = self.view_entry_list(user=self.superuser)
        response_soup = BeautifulSoup(list_response.content, 'html.parser')
        row_div = response_soup.find('div', class_='blog-entry-row')
        self.assertIsNotNone(row_div, "A superuser can see the draft")

    def test_order_drafts_first_then_published_by_date(self):
        # Ordering is finicky if the test creates entries too quickly, so we
        # have to throttle it with sleep...
        # To ensure draft ordering is correct, we'll create the draft neither
        # first nor last.
        self.create_entry(title="Entry 1")
        time.sleep(0.01)
        self.create_entry(title="Entry 2", is_published=False)
        time.sleep(0.01)
        self.create_entry(title="Entry 3")

        list_response = self.view_entry_list(user=self.superuser)
        response_soup = BeautifulSoup(list_response.content, 'html.parser')
        row_divs = response_soup.find_all('div', class_='blog-entry-row')
        listed_titles = [
            row_div.find('h3').find('a').contents[0] for row_div in row_divs]
        self.assertListEqual(
            ["Entry 2", "Entry 3", "Entry 1"], listed_titles,
            "Draft first, then newer public entry, then older public entry")

    def test_pagination(self):
        # Ordering is finicky if the test creates entries too quickly, so we
        # have to throttle it with sleep...
        # There are 10 entries per page. We make 10*x + 1 entries to test that
        # the last page is allowed to have only 1 entry. (The Django paginator
        # has a setting to merge the last 2 pages when the last page is small
        # enough.)
        for n in range(1, 21+1):
            self.create_entry(title="E{n}".format(n=n))
            time.sleep(0.01)

        list_response = self.client.get(
            resolve_url('blog:entry_list'))
        response_soup = BeautifulSoup(list_response.content, 'html.parser')
        row_divs = response_soup.find_all('div', class_='blog-entry-row')
        listed_titles = [
            row_div.find('h3').find('a').contents[0] for row_div in row_divs]
        self.assertListEqual(
            ["E21", "E20", "E19", "E18", "E17",
             "E16", "E15", "E14", "E13", "E12"],
            listed_titles,
            "First page lists entries as expected")

        list_response = self.client.get(
            resolve_url('blog:entry_list') + '?page=2')
        response_soup = BeautifulSoup(list_response.content, 'html.parser')
        row_divs = response_soup.find_all('div', class_='blog-entry-row')
        listed_titles = [
            row_div.find('h3').find('a').contents[0] for row_div in row_divs]
        self.assertListEqual(
            ["E11", "E10", "E9", "E8", "E7", "E6", "E5", "E4", "E3", "E2"],
            listed_titles,
            "Second page lists entries as expected")

        list_response = self.client.get(
            resolve_url('blog:entry_list') + '?page=3')
        response_soup = BeautifulSoup(list_response.content, 'html.parser')
        row_divs = response_soup.find_all('div', class_='blog-entry-row')
        listed_titles = [
            row_div.find('h3').find('a').contents[0] for row_div in row_divs]
        self.assertListEqual(
            ["E1"],
            listed_titles,
            "Third page lists entries as expected")
