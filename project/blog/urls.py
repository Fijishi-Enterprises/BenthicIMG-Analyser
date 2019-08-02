from __future__ import unicode_literals

from django.conf.urls import include, url

from . import views


urlpatterns = [
    # Customizations of andablog views.
    # These come before the andablog URL include, because
    # in urlpatterns, URLs that come first take precedence.
    url(r'^$',
        views.EntriesList.as_view(),
        name='entrylist'),

    url(r'', include('andablog.urls')),
]
