from django.conf.urls import url
from . import views

urlpatterns = [
    url(r'^(?P<source_id>\d+)/$', views.visualize_source, name="visualize_source"),
    url(r'^(?P<source_id>\d+)/delete/$', views.browse_delete, name="browse_delete"),
    url(r'^(?P<source_id>\d+)/browse_download/$', views.browse_download, name="browse_download"),
    url(r'^(?P<source_id>\d+)/metadata_edit_ajax/$', views.metadata_edit_ajax, name="metadata_edit_ajax"),
#    url(r'^(?P<source_id>\d+)/load_view_ajax$', views.visualize_source_ajax, name="visualize_source_ajax"),
    url(r'^(?P<source_id>\d+)/statistics', views.generate_statistics, name="statistics"),
    url(r'^(?P<source_id>\d+)/csv_annotations/$', views.export_annotations, name="export_annotations"),
    url(r'^(?P<source_id>\d+)/csv_statistics/$', views.export_statistics, name="export_statistics"),
    url(r'^(?P<source_id>\d+)/csv_abundances/$', views.export_abundance, name="export_abundance"),
    url(r'^(?P<source_id>\d+)/export/$', views.export_menu, name="export_menu"),
]
