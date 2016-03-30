from django.conf.urls import patterns, url

urlpatterns = patterns('',
    url(r'^map/$', 'map.views.map', name="map"),
)