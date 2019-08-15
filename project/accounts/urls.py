from __future__ import unicode_literals

from django.conf.urls import include, url
from django.views.generic.base import TemplateView
from . import views
from .forms import AuthenticationForm


urlpatterns = [
    # Customizations of django-registration and django.contrib.auth views.
    # These come before the django-registration URL include, because
    # in urlpatterns, URLs that come first take precedence.
    url(r'^login/$',
        views.LoginView.as_view(
            template_name='registration/login.html',
            authentication_form=AuthenticationForm,
        ),
        name='login'),
    url(r'^register/$',
        views.register,
        name='registration_register'),

    # django.contrib.auth URLs, such as login and password reset.
    url(r'', include('django.contrib.auth.urls')),

    # django-registration URLs, such as account activation.
    #
    # These are included AFTER django.contrib.auth URLs so that
    # django.contrib.auth wins out in case of URL pattern conflicts.
    # This is key because this registration include also includes the auth
    # URLs, except with different names that make things break.
    # The one thing that django-registration truly overrides is the
    # register view, but we have our own customization on top of that, so
    # we define register above auth anyway.
    #
    # (TODO: The above comment would no longer apply once we upgrade to
    # django-registration 3.0, which no longer tries to include the auth URLs
    # for us.)
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

    # Profile views.
    url(r'^profile/list/$',
        views.profile_list,
        name='profile_list'),
    url(r'^profile/detail/(?P<user_id>\d+)/$',
        views.profile_detail,
        name='profile_detail'),
    url(r'^profile/edit/$',
        views.ProfileEditView.as_view(),
        name='profile_edit'),
    url(r'^profile/edit/cancel/$',
        views.profile_edit_cancel,
        name='profile_edit_cancel'),

    # Other accounts related views.
    url(r'^emailall/$',
        views.email_all,
        name='emailall'),
]
