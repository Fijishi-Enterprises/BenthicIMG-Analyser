from django.urls import reverse

from lib.tests.utils import BasePermissionTest
from .models import NewsItem


class PermissionTest(BasePermissionTest):

    def test_newsfeed_details(self):
        news_item = NewsItem(
            source_id=self.source.pk,
            source_name=self.source.name,
            user_id=self.user.pk,
            user_username=self.user.username,
            message="This is a message",
            category='source',
        )
        news_item.save()
        url = reverse('newsfeed_details', args=[news_item.pk])
        template = 'newsfeed/details.html'

        self.source_to_private()
        self.assertPermissionLevel(url, self.SOURCE_EDIT, template=template)
        self.source_to_public()
        self.assertPermissionLevel(url, self.SOURCE_EDIT, template=template)

    def test_newsfeed_global(self):
        url = reverse('newsfeed_global')
        template = 'newsfeed/global.html'

        self.assertPermissionLevel(
            url, self.SUPERUSER, template=template,
            deny_type=self.REQUIRE_LOGIN)
