from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django.views.generic import TemplateView

import lib.views as lib_views
import vision_backend.views as backend_views


urlpatterns = [
    # These apps don't have uniform prefixes. We'll trust them to provide
    # their own non-clashing URL patterns.
    path('', include('annotations.urls')),
    path('', include('calcification.urls', namespace='calcification')),
    path('', include('images.urls')),
    path('', include('labels.urls')),

    path('accounts/', include('accounts.urls')),
    path('newsfeed/', include('newsfeed.urls')),
    path('async_media/',
         include('async_media.urls', namespace='async_media')),
    path('blog/', include('blog.urls', namespace='blog')),
    path('source/<int:source_id>/browse/', include('visualization.urls')),
    path('source/<int:source_id>/export/', include('export.urls')),
    path('source/<int:source_id>/upload/', include('upload.urls')),
    path('source/<int:source_id>/backend/', include('vision_backend.urls')),

    path('admin/doc/', include('django.contrib.admindocs.urls')),
    path('admin/', admin.site.urls),

    path('', lib_views.index, name='index'),
    path('about/',
         TemplateView.as_view(template_name='lib/about.html'),
         name='about'),
    path('release/',
         TemplateView.as_view(template_name='lib/release_notes.html'),
         name='release'),

    # Flatpages, such as the help page
    path('pages/', include('flatpages_custom.urls', namespace='pages')),

    # markdownx editor AJAX functionality (content preview and image upload).
    path('markdownx/', include('markdownx.urls')),

    # API
    path('api/', include('api_core.urls', namespace='api')),
    path('api_management/',
         include('api_management.urls', namespace='api_management')),

    # "Secret" dev views
    path('admin_tools/', lib_views.admin_tools, name='admin_tools'),
    path('error_500_test/', lib_views.error_500_test, name='error_500_test'),
    path('nav_test/<int:source_id>/', lib_views.nav_test, name='nav_test'),
    path('backend_overview/',
         backend_views.backend_overview,
         name='backend_overview'),
    path('cm_test/', backend_views.cm_test, name='cm_test'),
    
    # Internationalization
    path('i18n/', include('django.conf.urls.i18n')),
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
