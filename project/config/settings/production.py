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

# Absolute path to the directory which static files should be collected to.
# Example: "/home/media/media.lawrence.com/static/"
#
# To collect static files in STATIC_ROOT, first ensure that your static files
# are in apps' "static/" subdirectories and in STATICFILES_DIRS. Then use the
# collectstatic management command.
# Don't put anything in STATIC_ROOT manually.
#
# Then, use your web server's settings to serve STATIC_ROOT at the STATIC_URL.
# This is done outside of Django, but the docs have some implementation
# suggestions. Basically, you either serve directly from the STATIC_ROOT
# with nginx, or you push the STATIC_ROOT to a separate static-file server
# and serve from there.
# https://docs.djangoproject.com/en/dev/howto/static-files/deployment/
#
# This only applies for DEBUG = False. When DEBUG = True, static files
# are served automagically with django.contrib.staticfiles.views.serve().
STATIC_ROOT = SITE_DIR.child('static_serve')

WSGI_APPLICATION = 'config.wsgi.application'

