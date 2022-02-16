from django.urls import path

from . import views


app_name = 'cpce'

urlpatterns = [
    path('upload/',
         views.upload_page, name="upload_page"),
    path('upload_preview_ajax/',
         views.upload_preview_ajax,
         name="upload_preview_ajax"),
    path('upload_confirm_ajax/',
         views.CpcAnnotationsUploadConfirmView.as_view(),
         name="upload_confirm_ajax"),

    path('export_prepare_ajax/',
         views.export_prepare_ajax,
         name="export_prepare_ajax"),
    path('export_serve/',
         views.export_serve,
         name="export_serve"),
]
