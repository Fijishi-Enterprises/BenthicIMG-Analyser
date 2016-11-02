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
