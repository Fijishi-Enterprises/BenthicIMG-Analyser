from django.urls import path

from . import views


urlpatterns = [
    path('classifier/<int:classifier_id>/deploy/',
         views.Deploy.as_view(), name='deploy'),
    path('deploy_job/<int:job_id>/status/',
         views.DeployStatus.as_view(), name='deploy_status'),
    path('deploy_job/<int:job_id>/result/',
         views.DeployResult.as_view(), name='deploy_result'),
]
