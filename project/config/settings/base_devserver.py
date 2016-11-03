# Base settings for a development server.
# This isn't a standalone settings file. You also need to import
# one of the 'storage' settings files to have a complete set of settings.

from .base import *



DEBUG = True

# Instead of routing emails through a mail server,
# just print emails to the console.
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# Hosts/domain names that are valid for this site.
# "*" matches anything, ".example.com" matches example.com and all subdomains
#
# When DEBUG is True and ALLOWED_HOSTS is empty,
# the host is validated against ['localhost', '127.0.0.1', '[::1]'].
# https://docs.djangoproject.com/en/dev/ref/settings/#allowed-hosts
ALLOWED_HOSTS = []
