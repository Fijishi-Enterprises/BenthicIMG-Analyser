from django.conf.urls import url

from . import views


urlpatterns = [
    # We've customized 2 out of 2 andablog views, so we don't need to
    # `include` the andablog views on top of this.
    url(r'^$',
        views.EntriesList.as_view(
            template_name='blog/entry_list.html'),
        name='entry_list'),
    url(r'^(?P<slug>[A-Za-z0-9-_]+)/$',
        views.EntryDetail.as_view(
            template_name='blog/entry_detail.html'),
        name='entry_detail'),
]
