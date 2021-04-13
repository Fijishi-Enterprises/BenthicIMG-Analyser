from django.conf.urls import include, url

from . import views


urlpatterns = [
    url(r'^token_auth/$',
        views.ObtainAuthToken.as_view(), name='token_auth'),
    url(r'', include('vision_backend_api.urls')),
]
