from django.conf.urls import url
from . import views

urlpatterns = [
    url(r'^images/$',
        views.browse_images, name="browse_images"),
    url(r'^metadata/$',
        views.edit_metadata, name="edit_metadata"),
    url(r'^patches/$',
        views.browse_patches, name="browse_patches"),

    url(r'^delete_ajax/$',
        views.browse_delete_ajax, name="browse_delete_ajax"),
    url(r'^edit_metadata_ajax/$',
        views.edit_metadata_ajax, name="edit_metadata_ajax"),

    url(r'^statistics/$',
        views.generate_statistics, name="statistics"),
    url(r'^csv_abundances/$',
        views.export_abundance, name="export_abundance"),
]
