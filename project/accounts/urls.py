# This urls file has:
# - userena's urlpatterns
# - our urlpatterns which override userena's urlpatterns
# - other accounts-related urls

from django.conf.urls import url, include
from django.contrib.auth import views as auth_views
from userena import views as userena_views
from . import views

urlpatterns = [
    # Overriding userena's views.
    # To pull this off, we must match our regex with theirs exactly
    # to mask userena's URLs. We must do this as long as we're still
    # including userena.urls.
    url(r'^(?P<username>[\@\.\w-]+)/password/$',
       views.userena_password_change),
    url(r'^(?P<username>[\@\.\w-]+)/password/complete/$',
       views.userena_password_change_done),
    url(r'^signin/$', userena_views.signin,
        {'template_name': 'userena/signin_form.html'},
        name='signin'),
    url(r'^signup/$', views.user_add,
        name='signup'),


    # These views are replacements of userena views, but the URL doesn't
    # match. This means the userena URLs can still be reached by URL typing,
    # unless we mask those URLs with separate views that redirect to these
    # views.
    url(r'^password_change/$', auth_views.password_change,
        {'template_name': 'accounts/password_change.html'},
        name='password_change'),
    url(r'^password_change/done/$', auth_views.password_change_done,
        {'template_name': 'accounts/password_change_done.html'},
        name='password_change_done'),


    # These views aren't concerned with overriding userena ones.
    url(r'^emailall/$', views.email_all,
        name='emailall'),


    # Include userena urls after our urls, so ours take precedence
    url(r'', include('userena.urls')),
]
