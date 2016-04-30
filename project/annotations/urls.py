from django.conf.urls import url
from . import views

urlpatterns = [
    url(r'^labels/$', views.label_list, name="label_list"),
    url(r'^labels/(?P<label_id>\d+)/$', views.label_main, name="label_main"),
    url(r'^labels/new/$', views.label_new, name="label_new"),
    url(r'^labelsets/$', views.labelset_list, name="labelset_list"),

    url(r'^source/(?P<source_id>\d+)/labelset/$', views.labelset_main, name="labelset_main"),
    url(r'^source/(?P<source_id>\d+)/labelset/new/$', views.labelset_new, name="labelset_new"),
    url(r'^source/(?P<source_id>\d+)/labelset/edit/$', views.labelset_edit, name="labelset_edit"),

    url(r'^image/(?P<image_id>\d+)/annotation_tool/$', views.annotation_tool, name="annotation_tool"),
    url(r'^annotation_tool_settings_save/$', views.annotation_tool_settings_save, name="annotation_tool_settings_save"),
    url(r'^image/(?P<image_id>\d+)/save_annotations_ajax/$', views.save_annotations_ajax, name="save_annotations_ajax"),
    url(r'^image/(?P<image_id>\d+)/is_annotation_all_done_ajax/$', views.is_annotation_all_done_ajax, name="is_annotation_all_done_ajax"),

    url(r'^image/(?P<image_id>\d+)/annotation_area_edit/$', views.annotation_area_edit, name="annotation_area_edit"),
    url(r'^image/(?P<image_id>\d+)/annotation_history/$', views.annotation_history, name="annotation_history"),
]