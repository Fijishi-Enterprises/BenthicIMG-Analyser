from django.urls import path
from . import views

urlpatterns = [
    path('',
         views.upload_portal, name="upload_portal"),

    path('images/',
         views.upload_images, name="upload_images"),
    path('images_preview_ajax/',
         views.upload_images_preview_ajax, name="upload_images_preview_ajax"),
    path('images_ajax/',
         views.upload_images_ajax, name="upload_images_ajax"),

    path('metadata/',
         views.upload_metadata, name="upload_metadata"),
    path('metadata_preview_ajax/',
         views.upload_metadata_preview_ajax, name="upload_metadata_preview_ajax"),
    path('metadata_ajax/',
         views.upload_metadata_ajax, name="upload_metadata_ajax"),

    path('annotations_csv/',
         views.upload_annotations_csv, name="upload_annotations_csv"),
    path('annotations_csv_preview_ajax/',
         views.upload_annotations_csv_preview_ajax,
         name="upload_annotations_csv_preview_ajax"),
    path('annotations_csv_confirm_ajax/',
         views.AnnotationsUploadConfirmView.as_view(),
         name="upload_annotations_csv_confirm_ajax"),
]
