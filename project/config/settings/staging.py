# Settings for a test environment which is as close to production as possible.

from .production import *



DEBUG = True

# Instead of routing emails through a mail server,
# just write emails to the filesystem.
EMAIL_BACKEND = 'django.core.mail.backends.filebased.EmailBackend'
EMAIL_FILE_PATH = SITE_DIR.child('tmp/emails')

# Hosts/domain names that are valid for this site.
# "*" matches anything, ".example.com" matches example.com and all subdomains
#
# TODO: Once we upgrade to Django 1.9.11, we may or may not have to update
# this to accommodate test runs. Read here:
# https://docs.djangoproject.com/en/dev/topics/testing/advanced/#topics-testing-advanced-multiple-hosts
ALLOWED_HOSTS = ['.amazonaws.com']
