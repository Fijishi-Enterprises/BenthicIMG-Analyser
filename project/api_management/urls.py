from django.urls import path

from . import views


app_name = 'api_management'

urlpatterns = [
    path(r'jobs/',
         views.job_list, name='job_list'),
    path(r'jobs/<int:job_id>/',
         views.job_detail, name='job_detail'),
]
