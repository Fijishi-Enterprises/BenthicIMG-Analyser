from django.conf.urls import url
from . import views

urlpatterns = [
    url(r'^image/(?P<image_id>\d+)/annotation_tool/$', views.annotation_tool, name="annotation_tool"),
    url(r'^annotation_tool_settings_save/$', views.annotation_tool_settings_save, name="annotation_tool_settings_save"),
    url(r'^image/(?P<image_id>\d+)/save_annotations_ajax/$', views.save_annotations_ajax, name="save_annotations_ajax"),
    url(r'^image/(?P<image_id>\d+)/is_annotation_all_done_ajax/$', views.is_annotation_all_done_ajax, name="is_annotation_all_done_ajax"),

    url(r'^image/(?P<image_id>\d+)/annotation_area_edit/$', views.annotation_area_edit, name="annotation_area_edit"),
    url(r'^image/(?P<image_id>\d+)/annotation_history/$', views.annotation_history, name="annotation_history"),
]