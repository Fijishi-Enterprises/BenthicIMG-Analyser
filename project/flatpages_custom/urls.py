from django.contrib.flatpages import views as flatpages_views
from django.urls import include, path


app_name = 'flatpages_custom'

urlpatterns = [
    # First, for flatpages which we may link from non-flatpages, we
    # specify the URLs individually so that we can assign URL names.
    path('help/',
         flatpages_views.flatpage, {'url': '/help/'},
         name='help'),

    # Then for all other flatpages, we use this include to generate the URLs.
    path('', include('django.contrib.flatpages.urls')),
]
