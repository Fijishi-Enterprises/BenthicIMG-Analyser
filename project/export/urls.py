from django.conf.urls import url
from . import views

urlpatterns = [
    url(r'^metadata/$',
        views.export_metadata, name="export_metadata"),
    url(r'^annotations_simple/$',
        views.export_annotations_simple, name="export_annotations_simple"),
    url(r'^annotations_full/$',
        views.export_annotations_full, name="export_annotations_full"),
]
