from django.conf.urls import include, url
from django.views.generic.base import TemplateView
from . import views


urlpatterns = [
    # Customizations of django-registration and django.contrib.auth views.
    # These come before the django-registration URL include, because
    # in urlpatterns, URLs that come first take precedence.
    url(r'^register/$',
        views.RegistrationView.as_view(),
        name='registration_register'),

    # django-registration URLs.
    # Includes django.contrib.auth pages (e.g. login, password reset)
    # and django-registration pages (e.g. account activation).
    url(r'', include('registration.backends.hmac.urls')),

    # Views for re-sending an activation email, in case it expired or got lost.
    url(r'^activation/resend/$',
        views.ActivationResendView.as_view(),
        name='activation_resend'),
    url(r'^activation/resend/complete/$',
        TemplateView.as_view(
            template_name='registration/activation_resend_complete.html'
        ),
        name='activation_resend_complete'),

    # Email-change views.
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

    # Other accounts related views.
    url(r'^emailall/$',
        views.email_all,
        name='emailall'),

    # TODO: Check if needed for user profile support
    # Include userena urls after our urls, so ours take precedence
    #url(r'', include('userena.urls')),
]
