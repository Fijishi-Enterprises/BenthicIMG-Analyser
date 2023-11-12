from urllib.parse import urlencode

from django import template
from django.conf import settings

register = template.Library()


@register.simple_tag
def google_maps_api_url(callback):
    url = 'https://maps.googleapis.com/maps/api/js'

    url_kwargs = dict()
    url_kwargs['callback'] = callback
    if settings.GOOGLE_MAPS_API_KEY:
        url_kwargs['key'] = settings.GOOGLE_MAPS_API_KEY

    url = url + '?' + urlencode(url_kwargs)

    return url
