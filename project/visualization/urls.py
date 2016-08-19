from django.conf.urls import url
from . import views

urlpatterns = [
    url(r'^images/$',
        views.browse_images, name="browse_images"),
    url(r'^metadata/$',
        views.edit_metadata, name="edit_metadata"),
    url(r'^patches/$',
        views.browse_patches, name="browse_patches"),

    # TODO: Check if needed
    #url(r'^(?P<source_id>\d+)/$', views.visualize_source, name="visualize_source"),

    url(r'^delete/$',
        views.browse_delete, name="browse_delete"),
    url(r'^download/$',
        views.browse_download, name="browse_download"),
    url(r'^edit_metadata_ajax/$',
        views.metadata_edit_ajax, name="metadata_edit_ajax"),

    url(r'^statistics/$',
        views.generate_statistics, name="statistics"),
    url(r'^export_annotations/$',
        views.export_annotations, name="export_annotations"),
    url(r'^export_statistics/$',
        views.export_statistics, name="export_statistics"),
    url(r'^csv_abundances/$',
        views.export_abundance, name="export_abundance"),
    url(r'^export_menu/$',
        views.export_menu, name="export_menu"),
]
