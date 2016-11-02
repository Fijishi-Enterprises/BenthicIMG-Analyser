# Settings for the public site.

from .base import *
from .storage_s3 import *



DEBUG = False

# People who get code error notifications.
# In the format [('Full Name', 'email@example.com'),
# ('Full Name', 'anotheremail@example.com')]
#
# This might be a candidate for the secrets file, but it's borderline,
# and it's also slightly messier to define a complex setting like this in JSON.
# So it's staying here for now.
#
# TODO: Get email working in production, then uncomment this.
ADMINS = [
#    ('Stephen', 'stephenjchan@gmail.com'),
#    ('Oscar', 'oscar.beijbom@gmail.com'),
#    ('CoralNet', 'coralnet@eng.ucsd.edu'),
]

# Not-necessarily-technical managers of the site. They get broken link
# notifications and other various emails.
MANAGERS = ADMINS

# Hosts/domain names that are valid for this site.
# "*" matches anything, ".example.com" matches example.com and all subdomains
# TODO: When server setup is more settled in, only allow one host/domain.
ALLOWED_HOSTS = ['.ucsd.edu', '.amazonaws.com', '127.0.0.1']

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



# [Custom setting]
# Verbosity of print messages printed by our unit tests' code. Note that
# this is different from Django's test runner's verbosity setting, which
# relates to messages printed by Django's test runner code.
#
# 0 means the unit tests won't print any additional messages.
#
# 1 means the unit tests will print additional messages as extra confirmation
# that things worked.
#
# There is no 2 for now, unless we see a need for it later.
UNIT_TEST_VERBOSITY = 0



# VISION BACKEND SETTINGS
# TODO: move to separate settings file.
SLEEP_TIME_BETWEEN_IMAGE_PROCESSING = 60 * 60
