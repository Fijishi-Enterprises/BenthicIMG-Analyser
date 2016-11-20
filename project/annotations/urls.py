from django.conf.urls import include, url
from . import views

general_urlpatterns = [
    url(r'^tool_settings_save_ajax/$',
        views.annotation_tool_settings_save,
        name="annotation_tool_settings_save"),
]

image_urlpatterns = [
    url(r'^tool/$',
        views.annotation_tool, name="annotation_tool"),
    url(r'^save_ajax/$',
        views.save_annotations_ajax, name="save_annotations_ajax"),
    url(r'^all_done_ajax/$',
        views.is_annotation_all_done_ajax, name="is_annotation_all_done_ajax"),
    url(r'^area_edit/$',
        views.annotation_area_edit, name="annotation_area_edit"),
    url(r'^history/$',
        views.annotation_history, name="annotation_history"),
]

urlpatterns = [
    url(r'^annotation/', include(general_urlpatterns)),
    url(r'^image/(?P<image_id>\d+)/annotation/', include(image_urlpatterns)),
]
