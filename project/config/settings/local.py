from .base import *



# Directory for any site related files, not just the repository.
SITE_DIR = PROJECT_DIR.ancestor(2)



DEBUG = True

# People who get code error notifications.
# In the format [('Full Name', 'email@example.com'),
# ('Full Name', 'anotheremail@example.com')]
ADMINS = []

# Hosts/domain names that are valid for this site.
# "*" matches anything, ".example.com" matches example.com and all subdomains
ALLOWED_HOSTS = ['*']

# Local time zone for this installation. All choices can be found here:
# http://en.wikipedia.org/wiki/List_of_tz_zones_by_name (although not all
# systems may support all possibilities). When USE_TZ is True, this is
# interpreted as the default user time zone.
TIME_ZONE = 'America/Los_Angeles'

# Not-necessarily-technical managers of the site. They get broken link
# notifications and other various emails.
MANAGERS = ADMINS

# Instead of routing emails through a mail server,
# just print emails to the console.
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# Default file storage mechanism that holds media.
DEFAULT_FILE_STORAGE = 'lib.storage_backends.MediaStorageLocal'

# easy_thumbnails 3rd party app:
# Default file storage for saving generated thumbnails.
#
# The only downside of not using the app's provided storage class is that
# the THUMBNAIL_MEDIA_ROOT and THUMBNAIL_MEDIA_URL settings won't work
# (we'd have to apply them manually). We aren't using these settings, though.
THUMBNAIL_DEFAULT_STORAGE = DEFAULT_FILE_STORAGE

# Absolute filesystem path to the directory that will hold user-uploaded files.
# Example: "/home/media/media.lawrence.com/media/"
# If user-uploaded files live in a separate server such as AWS, then
# this setting doesn't apply.
MEDIA_ROOT = SITE_DIR.child('media')

# URL that handles the media served from MEDIA_ROOT.
# Example: "http://media.lawrence.com/media/"
MEDIA_URL = '/media/'

# [Custom setting]
# Absolute filesystem path to the directory that will
# hold input and output files for backend processing tasks.
# This directory is best kept out of the repository.
# Example: "/home/mysite_processing/"
PROCESSING_ROOT = SITE_DIR.child('processing')

# Absolute path to the directory which static files should be collected to.
# Example: "/home/media/media.lawrence.com/static/"
#
# To collect static files here, first ensure that your static files are
# in apps' "static/" subdirectories and in STATICFILES_DIRS. Then use the
# collectstatic management command.
# Don't put anything in this directory manually.
#
# Then, use your web server's settings to serve STATIC_ROOT at the STATIC_URL.
# This is done outside of Django, but the docs have some implementation
# suggestions.
# https://docs.djangoproject.com/en/dev/howto/static-files/deployment/
#
# This only applies for DEBUG = False. When DEBUG = True, static files
# are served automagically with django.contrib.staticfiles.views.serve().
STATIC_ROOT = SITE_DIR.child('static_serve')

# The maximum size (in bytes) that an upload will be before it
# gets streamed to the file system.
FILE_UPLOAD_MAX_MEMORY_SIZE = 52428800  # 50 MB



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
SLEEP_TIME_BETWEEN_IMAGE_PROCESSING = 5 * 60