# General-use custom template tags and filters.


import json
import pytz
import urllib
from datetime import datetime
from django import template
from django.conf import settings
from django.contrib.staticfiles.templatetags.staticfiles import StaticFilesNode
from django.utils import timezone
from django.utils.safestring import mark_safe

register = template.Library()


# Usage: {% get_form_media form as form_media %}
@register.simple_tag
def get_form_media(form):
    return dict(js=form.media._js, css=form.media._css)


@register.simple_tag
def google_maps_api_url(callback):
    url = 'https://maps.googleapis.com/maps/api/js'

    url_kwargs = dict()
    url_kwargs['callback'] = callback
    if settings.GOOGLE_MAPS_API_KEY:
        url_kwargs['key'] = settings.GOOGLE_MAPS_API_KEY

    url = url + '?' + urllib.urlencode(url_kwargs)

    return url


# jsonify
#
# Turn a Django template variable into a JSON string and return the result.
# mark_safe() is used to prevent escaping of quote characters
# in the JSON (so they stay as quotes, and don't become &quot;).
#
# Usage: <script> AnnotationToolHelper.init({{ labels|jsonify }}); </script>
#
# Basic idea from:
# http://djangosnippets.org/snippets/201/
@register.filter
def jsonify(object):
    return mark_safe(json.dumps(object))


@register.simple_tag
def get_maintenance_time():
    try:
        with open(settings.MAINTENANCE_STATUS_FILE_PATH, 'r') as json_file:
            params = json.load(json_file)
            naive_utc_time = datetime.utcfromtimestamp(params['timestamp'])
            return timezone.make_aware(naive_utc_time, pytz.timezone("UTC"))
    except IOError:
        return None


@register.filter
def time_is_past(datetime_obj):
    return datetime_obj < timezone.now()


@register.filter
def truncate_float(f):
    """
    Truncate a float to an int.

    This filter is useful because:
    1. The default `floatformat` template filter only does rounding,
    not truncation
    2. f.__int__ in the template gets a TemplateSyntaxError:
    "Variables and attributes may not begin with underscores"
    """
    return int(f)


# versioned_static
#
# Prevent undesired browser caching of static files (CSS, JS, etc.)
# by adding a version string after the filename in the link/script element.
# The version string is the last-modified time of the file, as a timezone
# agnostic Unix timestamp.
# So the version string changes (and thus, the browser re-fetches)
# if and only if the file has been modified.
#
# Usage: {% versioned_static "js/util.js" %}
# Example output: {{ STATIC_URL }}js/util.js?version=1035720937
#
# TODO: This is obsolete now that we use ManifestStaticFilesStorage.
# Replace all versioned_static uses with static, and delete this tag.
@register.tag('versioned_static')
def do_versioned_static(parser, token):
    return StaticFilesNode.handle_token(parser, token)
