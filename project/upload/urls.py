from django.conf.urls import url
from . import views

urlpatterns = [
    url(r'^$',
        views.upload_portal, name="upload_portal"),

    url(r'^images/$',
        views.image_upload, name="image_upload"),
    url(r'^images_preview_ajax/$',
        views.image_upload_preview_ajax, name="image_upload_preview_ajax"),
    url(r'^images_ajax/$',
        views.image_upload_ajax, name="image_upload_ajax"),

    url(r'^metadata/$',
        views.upload_metadata, name="upload_metadata"),
    url(r'^metadata_preview_ajax/$',
        views.upload_metadata_preview_ajax, name="upload_metadata_preview_ajax"),
    url(r'^metadata_ajax/$',
        views.upload_metadata_ajax, name="upload_metadata_ajax"),

    url(r'^annotations/$',
        views.upload_annotations, name="upload_annotations"),
    url(r'^annotations_preview_ajax/$',
        views.upload_annotations_preview_ajax, name="upload_annotations_preview_ajax"),
    url(r'^annotations_ajax/$',
        views.upload_annotations_ajax, name="upload_annotations_ajax"),
]
