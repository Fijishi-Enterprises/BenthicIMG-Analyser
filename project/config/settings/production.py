# Settings for the public site.

from .base import *
from .storage_s3 import *



DEBUG = False

# Hosts/domain names that Django should consider as valid.
# "*" matches anything, ".example.com" matches example.com and all subdomains
#
# With our nginx proxy_pass setup, Django ends up seeing a hostname of
# 127.0.0.1. nginx is the gatekeeper for the original host header.
# So for validating the original host header, see NGINX_ALLOWED_HOSTS.
#
# Although it doesn't seem to apply to us currently, here's some info about
# configuring this setting if unit tests have some special domain name logic:
# https://docs.djangoproject.com/en/dev/topics/testing/advanced/#topics-testing-advanced-multiple-hosts
ALLOWED_HOSTS = ['127.0.0.1']

# [Custom setting]
# Hosts that nginx should consider valid. Each string item should be a valid
# server_name string in an nginx config file:
# http://nginx.org/en/docs/http/server_names.html
#
# When you update this, run the makenginxconfig management command
# to regenerate the nginx config file.
NGINX_ALLOWED_HOSTS = ['coralnet.ucsd.edu']

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

