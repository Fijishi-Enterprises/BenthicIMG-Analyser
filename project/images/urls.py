from django.urls import include, path
from . import views

source_general_urlpatterns = [
    path('', views.source_list, name="source_list"),
    path('about/', views.source_about, name="source_about"),
    path('new/', views.source_new, name="source_new"),
    path('invites/', views.invites_manage, name="invites_manage"),
]

source_specific_urlpatterns = [
    path('', views.source_main, name="source_main"),
    path('edit/', views.source_edit, name="source_edit"),
    path('edit/cancel/', views.source_edit_cancel, name='source_edit_cancel'),
    path('admin/', views.source_admin, name="source_admin"),
    path('detail_box/', views.source_detail_box, name="source_detail_box"),
]

image_urlpatterns = [
    # Pages
    path('view/', views.image_detail, name="image_detail"),
    path('edit/', views.image_detail_edit, name="image_detail_edit"),

    # Actions
    path('delete/', views.image_delete, name="image_delete"),
    path('delete_annotations/',
         views.image_delete_annotations, name="image_delete_annotations"),
    path('regenerate_points/',
         views.image_regenerate_points, name="image_regenerate_points"),
    path('reset_point_generation_method/',
         views.image_reset_point_generation_method,
         name="image_reset_point_generation_method"),
    path('reset_annotation_area/',
         views.image_reset_annotation_area, name="image_reset_annotation_area"),
]

urlpatterns = [
    path('source/', include(source_general_urlpatterns)),
    path('source/<int:source_id>/', include(source_specific_urlpatterns)),
    path('image/<int:image_id>/', include(image_urlpatterns)),
]
