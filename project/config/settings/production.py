# Settings for the public site.

from .base import *
from .storage_s3 import *



DEBUG = False

# Hosts/domain names that are valid for this site.
# "*" matches anything, ".example.com" matches example.com and all subdomains
#
# Although it doesn't seem to apply to us currently, here's some info about
# configuring this setting if unit tests have some special domain name logic:
# https://docs.djangoproject.com/en/dev/topics/testing/advanced/#topics-testing-advanced-multiple-hosts
ALLOWED_HOSTS = ['coralnet.ucsd.edu']

# Use HTTPS.
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
# This setting is needed since our nginx config connects to Django with a
# non-HTTPS proxy_pass.
# https://docs.djangoproject.com/en/dev/ref/settings/#secure-proxy-ssl-header
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

WSGI_APPLICATION = 'config.wsgi.application'

