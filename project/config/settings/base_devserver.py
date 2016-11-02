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
ALLOWED_HOSTS = ['*']
