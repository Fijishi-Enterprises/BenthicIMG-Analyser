"""
WSGI config for this Django project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/dev/howto/deployment/wsgi/
"""

import os

from django.core.exceptions import ImproperlyConfigured
from django.core.wsgi import get_wsgi_application

# We could set a default settings module here, but we don't really
# have a one-size-fits-all settings module. So to avoid potential confusion,
# we'll just ensure the settings module can only come from an env-var.
if not os.environ.get('DJANGO_SETTINGS_MODULE'):
    raise ImproperlyConfigured(
        "Must set the DJANGO_SETTINGS_MODULE environment variable."
        " Example value: config.settings.staging")

application = get_wsgi_application()
