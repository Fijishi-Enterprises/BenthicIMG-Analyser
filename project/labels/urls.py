from django.conf.urls import url
from . import views

urlpatterns = [
    url(r'^labels/$', views.label_list, name="label_list"),
    url(r'^labels/(?P<label_id>\d+)/$', views.label_main, name="label_main"),
    url(r'^labels/new_ajax/$', views.label_new_ajax, name="label_new_ajax"),
    url(r'^labels/search/$', views.label_search_ajax,
        name="label_search_ajax"),

    url(r'^source/(?P<source_id>\d+)/labelset/$', views.labelset_main,
        name="labelset_main"),
    url(r'^source/(?P<source_id>\d+)/labelset/add/$', views.labelset_add,
        name="labelset_add"),
    url(r'^source/(?P<source_id>\d+)/labelset/edit/$', views.labelset_edit,
        name="labelset_edit"),
]
