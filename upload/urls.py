from django.conf.urls import url
from . import views

urlpatterns = [
    url(r'^source/(?P<source_id>\d+)/upload/$', views.image_upload, name="image_upload"),
    url(r'^source/(?P<source_id>\d+)/upload_preview_ajax/$', views.image_upload_preview_ajax, name="image_upload_preview_ajax"),
    url(r'^source/(?P<source_id>\d+)/annotation_file_process_ajax/$', views.annotation_file_process_ajax, name="annotation_file_process_ajax"),
    url(r'^source/(?P<source_id>\d+)/upload_ajax/$', views.image_upload_ajax, name="image_upload_ajax"),
    url(r'^source/(?P<source_id>\d+)/csv_file_process_ajax/$', views.csv_file_process_ajax, name="csv_file_process_ajax"),
    #url(r'^source/(?P<source_id>\d+)/ajax_upload_progress/$', views.ajax_upload_progress, name="ajax_upload_progress"),
    url(r'^source/(?P<source_id>\d+)/upload/annotations/$', views.upload_archived_annotations, name="annotation_upload"),
    url(r'^source/(?P<source_id>\d+)/upload/annotations/verify/$', views.verify_archived_annotations, name="annotation_upload_verify")
]
