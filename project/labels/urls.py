from django.urls import include, path
from . import views

label_general_urlpatterns = [
    path('list/', views.label_list, name="label_list"),
    path('list_search_ajax/', views.label_list_search_ajax,
         name="label_list_search_ajax"),
    path('new/', views.label_new, name="label_new"),
    path('new_ajax/', views.label_new_ajax, name="label_new_ajax"),
    path('add_search_ajax/', views.labelset_add_search_ajax,
         name="labelset_add_search_ajax"),
    path('duplicates/', views.duplicates_overview,
         name="labelset_duplicates"),
]

label_specific_urlpatterns = [
    path('', views.label_main, name="label_main"),
    path('example_patches_ajax/',
         views.label_example_patches_ajax, name="label_example_patches_ajax"),
    path('edit/', views.label_edit, name="label_edit"),
]

labelset_urlpatterns = [
    path('', views.labelset_main,
         name="labelset_main"),
    path('add/', views.labelset_add,
         name="labelset_add"),
    path('edit/', views.labelset_edit,
         name="labelset_edit"),
    path('import/', views.labelset_import,
         name="labelset_import"),
    path('import_preview_ajax/',
         views.labelset_import_preview_ajax,
         name="labelset_import_preview_ajax"),
    path('import_ajax/',
         views.labelset_import_ajax,
         name="labelset_import_ajax"),
]

urlpatterns = [
    path('label/', include(label_general_urlpatterns)),
    path('label/<int:label_id>/', include(label_specific_urlpatterns)),
    path('source/<int:source_id>/labelset/', include(labelset_urlpatterns)),
]
