from django.conf.urls import url
from . import views

urlpatterns = [
    url(r'^media_ajax/$', views.media_ajax,
        name="media_ajax"),
    url(r'^media_poll_ajax/$', views.media_poll_ajax,
        name="media_poll_ajax"),
]
