from django.conf.urls import url
from . import views

urlpatterns = [
    url(r'^metadata/$',
        views.export_metadata, name="export_metadata"),
    url(r'^annotations/$',
        views.export_annotations, name="export_annotations"),
    url(r'^annotations_cpc_create_ajax/$',
        views.export_annotations_cpc_create_ajax,
        name="export_annotations_cpc_create_ajax"),
    url(r'^annotations_cpc_serve/$',
        views.export_annotations_cpc_serve,
        name="export_annotations_cpc_serve"),
    url(r'^image_covers/$',
        views.export_image_covers, name="export_image_covers"),
    url(r'^labelset/$',
        views.export_labelset, name="export_labelset"),
]
