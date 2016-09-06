from django.conf.urls import url
from . import views

urlpatterns = [
    url(r'^labels/$', views.label_list, name="label_list"),
    url(r'^labels/(?P<label_id>\d+)/$', views.label_main, name="label_main"),
    url(r'^labels/new/$', views.label_new, name="label_new"),
    url(r'^labelsets/$', views.labelset_list, name="labelset_list"),

    url(r'^source/(?P<source_id>\d+)/labelset/$', views.labelset_main,
        name="labelset_main"),
    url(r'^source/(?P<source_id>\d+)/labelset/new/$', views.labelset_new,
        name="labelset_new"),
    url(r'^source/(?P<source_id>\d+)/labelset/edit/$', views.labelset_edit,
        name="labelset_edit"),
]
