from django.conf import settings
from django.conf.urls import include, patterns, url
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

    # Uncomment the admin/doc line below to enable admin documentation:
    # url(r'^admin/doc/', include('django.contrib.admindocs.urls')),

    # Uncomment the next line to enable the admin:
    # url(r'^admin/', include(admin.site.urls)),


)

if settings.DEBUG:
    urlpatterns += patterns('',
        (r'^media/(?P<path>.*)$',
         'django.views.static.serve',
         {'document_root': settings.MEDIA_ROOT, 'show_indexes': True, }),
)



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