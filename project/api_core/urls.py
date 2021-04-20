from django.urls import include, path

from . import views


app_name = 'api_core'

urlpatterns = [
    path('token_auth/',
         views.ObtainAuthToken.as_view(), name='token_auth'),
    path('', include('vision_backend_api.urls')),
]
