from django.urls import path
from . import views


app_name = 'async_media'

urlpatterns = [
    path('media_ajax/', views.media_ajax,
         name="media_ajax"),
    path('media_poll_ajax/', views.media_poll_ajax,
         name="media_poll_ajax"),
]
