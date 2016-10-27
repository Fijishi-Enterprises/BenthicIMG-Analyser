from django.conf.urls import url, include
from . import views

urlpatterns = [
    url(r'^emailall/$', views.email_all,
        name='emailall'),

    # django-registration URLs.
    # Includes django.contrib.auth pages (e.g. login, password reset)
    # and django-registration pages (e.g. account activation).
    url(r'', include('registration.backends.hmac.urls')),

    # TODO: Check if needed for user profile support
    # Include userena urls after our urls, so ours take precedence
    #url(r'', include('userena.urls')),
]
