from django.conf.urls import url

from . import views


urlpatterns = [
    url(r'^classifier/(?P<classifier_id>\d+)/deploy/$',
        views.Deploy.as_view(), name='deploy'),
    url(r'^deploy_job/(?P<job_id>\d+)/status/$',
        views.DeployStatus.as_view(), name='deploy_status'),
    url(r'^deploy_job/(?P<job_id>\d+)/result/$',
        views.DeployResult.as_view(), name='deploy_result'),
]
