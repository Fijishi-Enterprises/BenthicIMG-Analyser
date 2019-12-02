# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.shortcuts import render
from django.contrib.auth.decorators import permission_required
from lib.decorators import news_item_permission_required

from .models import NewsItem, NewsSubItem
from images.models import Source


@permission_required('is_superuser')
def global_feed(request):
    return render(request, 'newsfeed/global.html', {
        'news_items':
            [item.render_view() for item in
             NewsItem.objects.filter().order_by('-pk')]
    })


@news_item_permission_required('news_item_id', perm=Source.PermTypes.EDIT.code)
def one_event(request, news_item_id):
    return render(request, 'newsfeed/details.html', {
        'main': NewsItem.objects.get(id=news_item_id).render_view(),
        'subs': [item.render_view() for item in
                 NewsSubItem.objects.filter(news_item__id=news_item_id)]
    })
