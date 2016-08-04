from django.conf import settings
from django.conf.urls import include, url
from django.conf.urls.static import static
from django.contrib import admin
from django.views.generic import TemplateView

import lib.views as lib_views

urlpatterns = [
    url(r'^feedback/', include('bug_reporting.urls')),
    url(r'^images/', include('images.urls')),
    url(r'^visualization/', include('visualization.urls')),
    url(r'^annotations/', include('annotations.urls')),
    url(r'^requests/', include('requests.urls')),
    url(r'^upload/', include('upload.urls')),

    url(r'^admin/doc/', include('django.contrib.admindocs.urls')),
    url(r'^admin/', include(admin.site.urls)),

    url(r'^accounts/', include('accounts.urls')),
    url(r'^messages/', include('userena.contrib.umessages.urls')),

    url(r'^$', lib_views.index, name='index'),

    url(r'^about/$',
        TemplateView.as_view(template_name='lib/about.html'),
        name='about',
    ),
    url(r'^contact/$', lib_views.contact, name='contact'),

    url(r'^nav_test/(?P<source_id>\d+)/$', lib_views.nav_test, name="nav_test"),

    # Internationalization
    url(r'^i18n/', include('django.conf.urls.i18n')),
]

# Serving media files in development.
# https://docs.djangoproject.com/en/dev/ref/views/#serving-files-in-development
#
# When in production, this doesn't do anything; you're expected to serve
# media via your web server software.
# https://docs.djangoproject.com/en/dev/howto/deployment/wsgi/modwsgi/#serving-files
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# Custom server-error handlers. Must be assigned in the root URLconf.
handler500 = lib_views.handler500