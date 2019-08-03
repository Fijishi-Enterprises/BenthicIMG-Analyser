from __future__ import unicode_literals

from django.conf.urls import url

from . import views


# andablog's internals find its URLs as 'andablog:...' at least once, so we
# need to retain that app name for URL matching purposes.
# (If we overrode everything in andablog that used 'andablog:...', this
# would no longer be necessary.)
app_name = 'andablog'

urlpatterns = [
    # We've customized 2 out of 2 andablog views, so we don't need to
    # `include` the andablog views on top of this.
    url(r'^$',
        views.EntriesList.as_view(),
        name='entrylist'),
    url(r'^(?P<slug>[A-Za-z0-9-_]+)/$',
        views.EntryDetail.as_view(),
        name='entrydetail'),
]
