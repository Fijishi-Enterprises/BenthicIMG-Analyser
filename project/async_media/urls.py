from django.conf.urls import url
from . import views

urlpatterns = [
    url(r'^thumbnails_ajax/$', views.thumbnails_ajax,
        name="thumbnails_ajax"),
    url(r'^thumbnails_poll_ajax/$', views.thumbnails_poll_ajax,
        name="thumbnails_poll_ajax"),
]
