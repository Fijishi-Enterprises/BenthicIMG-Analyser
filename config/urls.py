from django.conf import settings
from django.conf.urls import include, patterns, url
from django.conf.urls.static import static
from django.contrib import admin
from django.views.generic import TemplateView

urlpatterns = patterns('',
    (r'^feedback/', include('bug_reporting.urls')),
    (r'^images/', include('images.urls')),
    (r'^visualization/', include('visualization.urls')),
    (r'^annotations/', include('annotations.urls')),
    (r'^requests/', include('requests.urls')),
    (r'^upload/', include('upload.urls')),
    (r'^map/', include('map.urls')),

    (r'^admin/doc/', include('django.contrib.admindocs.urls')),
    (r'^admin/', include(admin.site.urls)),

    (r'^accounts/', include('accounts.urls')),
    (r'^messages/', include('userena.contrib.umessages.urls')),

    url(r'^$', 'lib.views.index', name='index'),

    url(r'^about/$',
        TemplateView.as_view(template_name='static/about.html'),
        name='about',
    ),
    url(r'^contact/$', 'lib.views.contact', name='contact'),

    # Internationalization
    (r'^i18n/', include('django.conf.urls.i18n')),
)

# Serving media files in development.
# https://docs.djangoproject.com/en/dev/ref/views/#serving-files-in-development
#
# When in production, this doesn't do anything; you're expected to serve
# media via your web server software.
# https://docs.djangoproject.com/en/dev/howto/deployment/wsgi/modwsgi/#serving-files
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)



# Custom server-error handlers. Should be assigned to handler500,
# handler404, etc. in the root URLconf.

def handler500(request):
    """
    500 error handler which includes ``request`` in the context.

    Templates: `500.html`
    Context: None
    """
    from django.template import Context, loader
    from django.http import HttpResponseServerError

    t = loader.get_template('500.html')
    return HttpResponseServerError(t.render(Context({
        'request': request,
    })))