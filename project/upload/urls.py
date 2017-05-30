from django.conf.urls import url
from . import views

urlpatterns = [
    url(r'^$',
        views.upload_portal, name="upload_portal"),

    url(r'^images/$',
        views.upload_images, name="upload_images"),
    url(r'^images_preview_ajax/$',
        views.upload_images_preview_ajax, name="upload_images_preview_ajax"),
    url(r'^images_ajax/$',
        views.upload_images_ajax, name="upload_images_ajax"),

    url(r'^metadata/$',
        views.upload_metadata, name="upload_metadata"),
    url(r'^metadata_preview_ajax/$',
        views.upload_metadata_preview_ajax, name="upload_metadata_preview_ajax"),
    url(r'^metadata_ajax/$',
        views.upload_metadata_ajax, name="upload_metadata_ajax"),

    url(r'^annotations_csv/$',
        views.upload_annotations_csv, name="upload_annotations_csv"),
    url(r'^annotations_csv_preview_ajax/$',
        views.upload_annotations_csv_preview_ajax,
        name="upload_annotations_csv_preview_ajax"),
    url(r'^annotations_cpc/$',
        views.upload_annotations_cpc, name="upload_annotations_cpc"),
    url(r'^annotations_cpc_preview_ajax/$',
        views.upload_annotations_cpc_preview_ajax,
        name="upload_annotations_cpc_preview_ajax"),
    # This is the final step for both CSV and CPC.
    # TODO: This could use a more descriptive name. 'confirm' maybe.
    url(r'^annotations_ajax/$',
        views.upload_annotations_ajax, name="upload_annotations_ajax"),
]
