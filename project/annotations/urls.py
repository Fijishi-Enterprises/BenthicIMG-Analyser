from django.urls import include, path
from . import views

general_urlpatterns = [
    path('tool_settings_save_ajax/',
         views.annotation_tool_settings_save,
         name="annotation_tool_settings_save"),
]

image_urlpatterns = [
    path('tool/',
         views.annotation_tool, name="annotation_tool"),
    path('save_ajax/',
         views.save_annotations_ajax, name="save_annotations_ajax"),
    path('all_done_ajax/',
         views.is_annotation_all_done_ajax, name="is_annotation_all_done_ajax"),
    path('area_edit/',
         views.annotation_area_edit, name="annotation_area_edit"),
    path('history/',
         views.annotation_history, name="annotation_history"),
]

urlpatterns = [
    path('annotation/', include(general_urlpatterns)),
    path('image/<int:image_id>/annotation/', include(image_urlpatterns)),
]
