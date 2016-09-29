# General-use custom template tags and filters.


import json
import os.path
from datetime import datetime, timedelta
from django import template
from django.conf import settings
from django.contrib.staticfiles import finders
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
def jsonify(object):
    return mark_safe(json.dumps(object))


# Usage: {% set_maintenance_time "9:00 PM" as maintenance_time %}
@register.simple_tag
def set_maintenance_time(datetime_str):

    # Acceptable datetime formats.
    datetime_format_strs = dict(
        time = '%I:%M %p',                        # 12:34 PM
        day_and_time = '%b %d %I:%M %p',          # Jun 24 12:34 PM
        year_day_and_time = '%Y %b %d %I:%M %p',  # 2008 Jun 24 12:34 PM
    )
    datetime_obj = None
    now = timezone.now()

    # Parse the input, trying each acceptable datetime format.
    # Then infer the full date and time.
    for key, datetime_format_str in datetime_format_strs.iteritems():
        try:
            input = datetime.strptime(datetime_str, datetime_format_str)
            input = timezone.make_aware(input, timezone.get_current_timezone())

            if key == 'time':
                # Just the hour and minute were given.
                naive_datetime_obj = datetime(
                    now.year, now.month, now.day, input.hour, input.minute)
                datetime_obj = timezone.make_aware(
                    naive_datetime_obj, timezone.get_current_timezone())
                # To find whether the intended day is yesterday,
                # today, or tomorrow, assume that the admin meant a time
                # within 12 hours (either way) from now.
                if datetime_obj - now > timedelta(0.5):
                    # e.g. datetime_obj = 11 PM, now = 1 AM
                    # Assume datetime_obj should be in the previous day,
                    # meaning we went under maintenance 2 hours ago.
                    datetime_obj = datetime_obj - timedelta(1)
                elif now - datetime_obj > timedelta(0.5):
                    # e.g. datetime_obj = 1 AM, now = 11 PM
                    # Assume datetime_obj should be in the next day,
                    # meaning we plan to go under maintenance in 2 hours.
                    datetime_obj = datetime_obj + timedelta(1)
            elif key == 'day_and_time':
                # The month, day, hour, and minute were given.
                naive_datetime_obj = datetime(
                    now.year, input.month, input.day,
                    input.hour, input.minute)
                datetime_obj = timezone.make_aware(
                    naive_datetime_obj, timezone.get_current_timezone())
                # Unlike the 'time' case, we won't bother dealing with
                # the 'maintenance next year' or 'maintenance last year'
                # corner case here. Adding/subtracting 1 year is sketchy
                # due to leap years.
                # Just be sure to use the 'year_day_and_time' case if it's
                # close to the new year.
            elif key == 'year_day_and_time':
                # The full date and time were given.
                datetime_obj = input

            # We've got the date and time, so we're done.
            break

        except ValueError:
            continue

    return datetime_obj


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
@register.simple_tag
def versioned_static(relative_path):
    if settings.DEBUG:
        # Find file in development environment
        absolute_path = finders.find(relative_path)
    else:
        # Find file in production environment
        absolute_path = os.path.join(settings.STATIC_ROOT, relative_path)

    return '%s?version=%s' % (
        os.path.join(settings.STATIC_URL, relative_path),
        int(os.path.getmtime(absolute_path))
        )