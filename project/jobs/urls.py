from django.urls import path

from . import views


app_name = 'jobs'

urlpatterns = [
    path(r'jobs/admin_dashboard/',
         views.admin_dashboard, name='admin_dashboard'),
    path(r'source/<int:source_id>/jobs/',
         views.source_dashboard, name='source_dashboard'),
]
