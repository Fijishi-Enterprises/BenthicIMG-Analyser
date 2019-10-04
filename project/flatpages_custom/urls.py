from __future__ import unicode_literals

from django.conf.urls import include, url
from django.contrib.flatpages import views as flatpages_views


urlpatterns = [
    # First, for flatpages which we may link from non-flatpages, we
    # specify the URLs individually so that we can assign URL names.
    url(r'^help/$',
        flatpages_views.flatpage, {'url': '/help/'},
        name='help'),

    # Then for all other flatpages, we use this include to generate the URLs.
    url(r'', include('django.contrib.flatpages.urls')),
]
