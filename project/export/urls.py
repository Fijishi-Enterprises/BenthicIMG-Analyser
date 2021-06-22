from django.urls import path
from . import views

urlpatterns = [
    path('metadata/',
         views.export_metadata, name="export_metadata"),
    path('annotations/',
         views.export_annotations, name="export_annotations"),
    path('annotations_cpc_create_ajax/',
         views.export_annotations_cpc_create_ajax,
         name="export_annotations_cpc_create_ajax"),
    path('annotations_cpc_serve/',
         views.export_annotations_cpc_serve,
         name="export_annotations_cpc_serve"),
    path('image_covers/',
         views.ImageCoversExportView.as_view(), name="export_image_covers"),
    path('labelset/',
         views.export_labelset, name="export_labelset"),
]
