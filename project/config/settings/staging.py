# Settings for a test environment which is as close to production as possible.

from .production import *



# Instead of routing emails through a mail server,
# just write emails to the filesystem.
EMAIL_BACKEND = 'django.core.mail.backends.filebased.EmailBackend'
EMAIL_FILE_PATH = SITE_DIR.child('tmp').child('emails')

# [Custom setting]
# Hosts that nginx should consider valid. Each string item should be a valid
# server_name string in an nginx config file:
# http://nginx.org/en/docs/http/server_names.html
#
# When you update this, run the makenginxconfig management command
# to regenerate the nginx config file.
NGINX_ALLOWED_HOSTS = ['ec2-35-162-62-60.us-west-2.compute.amazonaws.com']
