from django.conf.urls import url
from . import views

urlpatterns = [
    url(r'^source/(?P<source_id>\d+)/upload/$', views.image_upload, name="image_upload"),
    url(r'^source/(?P<source_id>\d+)/upload_preview_ajax/$', views.image_upload_preview_ajax, name="image_upload_preview_ajax"),
    url(r'^source/(?P<source_id>\d+)/annotation_file_process_ajax/$', views.annotation_file_process_ajax, name="annotation_file_process_ajax"),
    url(r'^source/(?P<source_id>\d+)/upload_ajax/$', views.image_upload_ajax, name="image_upload_ajax"),
    url(r'^source/(?P<source_id>\d+)/upload_metadata/$', views.upload_metadata, name="upload_metadata"),
    url(r'^source/(?P<source_id>\d+)/upload_metadata_preview_ajax/$', views.upload_metadata_preview_ajax, name="upload_metadata_preview_ajax"),
    url(r'^source/(?P<source_id>\d+)/upload_metadata_ajax/$', views.upload_metadata_ajax, name="upload_metadata_ajax"),
    url(r'^source/(?P<source_id>\d+)/upload/annotations/$', views.upload_archived_annotations, name="annotation_upload"),
    url(r'^source/(?P<source_id>\d+)/upload/annotations/verify/$', views.verify_archived_annotations, name="annotation_upload_verify")
]
