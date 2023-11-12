# General-use custom template tags and filters.

import datetime
import json

from django import template
from django.conf import settings
from django.utils import timezone
from django.utils.safestring import mark_safe

register = template.Library()


# Usage: {% get_form_media form as form_media %}
@register.simple_tag
def get_form_media(form):
    return dict(js=form.media._js, css=form.media._css)


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
def jsonify(obj):
    return mark_safe(json.dumps(obj))


@register.simple_tag
def get_maintenance_time():
    try:
        with open(settings.MAINTENANCE_STATUS_FILE_PATH, 'r') as json_file:
            params = json.load(json_file)
            return datetime.datetime.fromtimestamp(
                params['timestamp'], datetime.timezone.utc)
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
