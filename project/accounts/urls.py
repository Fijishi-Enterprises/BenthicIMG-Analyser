from django.conf.urls import include, url
from django.views.generic.base import TemplateView
from . import views


urlpatterns = [
    url(r'^email/change/$',
        views.EmailChangeView.as_view(),
        name='email_change'),
    url(r'^email/change/done/$',
        TemplateView.as_view(
            template_name='accounts/email_change_done.html'
        ),
        name='email_change_done'),
    url(r'^email/change/confirm/(?P<confirmation_key>[-:\w]+)/$',
        views.EmailChangeConfirmView.as_view(),
        name='email_change_confirm'),
    url(r'^email/change/complete/$',
        TemplateView.as_view(
            template_name='accounts/email_change_complete.html'
        ),
        name='email_change_complete'),

    url(r'^emailall/$',
        views.email_all,
        name='emailall'),

    # django-registration URLs.
    # Includes django.contrib.auth pages (e.g. login, password reset)
    # and django-registration pages (e.g. account activation).
    url(r'', include('registration.backends.hmac.urls')),

    # TODO: Check if needed for user profile support
    # Include userena urls after our urls, so ours take precedence
    #url(r'', include('userena.urls')),
]
