from django.conf.urls import include, url
from . import views

source_general_urlpatterns = [
    url(r'^$', views.source_list, name="source_list"),
    url(r'^about/$', views.source_about, name="source_about"),
    url(r'^new/$', views.source_new, name="source_new"),
    url(r'^invites/$', views.invites_manage, name="invites_manage"),
]

source_specific_urlpatterns = [
    url(r'^$', views.source_main, name="source_main"),
    url(r'^edit/$', views.source_edit, name="source_edit"),
    url(r'^edit/cancel/$', views.source_edit_cancel, name='source_edit_cancel'),
    url(r'^admin/$', views.source_admin, name="source_admin"),
    url(r'^detail_box/$', views.source_detail_box, name="source_detail_box"),
]

image_urlpatterns = [
    # Pages
    url(r'^view/$', views.image_detail, name="image_detail"),
    url(r'^edit/$', views.image_detail_edit, name="image_detail_edit"),

    # Actions
    url(r'^delete/$', views.image_delete, name="image_delete"),
    url(r'^delete_annotations/$',
        views.image_delete_annotations, name="image_delete_annotations"),
    url(r'^regenerate_points/$',
        views.image_regenerate_points, name="image_regenerate_points"),
    url(r'^reset_point_generation_method/$',
        views.image_reset_point_generation_method,
        name="image_reset_point_generation_method"),
    url(r'^reset_annotation_area/$',
        views.image_reset_annotation_area, name="image_reset_annotation_area"),
]

urlpatterns = [
    url(r'^source/', include(source_general_urlpatterns)),
    url(r'^source/(?P<source_id>\d+)/', include(source_specific_urlpatterns)),
    url(r'^image/(?P<image_id>\d+)/', include(image_urlpatterns)),
]
