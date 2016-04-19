# This urls file has:
# - userena's urlpatterns
# - our urlpatterns which override userena's urlpatterns
# - other accounts-related urls

from django.conf.urls import url, include
from userena import views as userena_views
from . import views

urlpatterns = [
    # Overriding userena urlpatterns
    url(r'^signin/$', userena_views.signin,
        {'template_name': 'userena/signin_form.html'},
        name='signin'),
    url(r'^signup/$', views.user_add,
        name='signup'),
    
    url(r'^emailall/$', views.email_all,
        name='emailall'),

    # Include userena urls after our urls, so ours take precedence
    url(r'', include('userena.urls')),
]
