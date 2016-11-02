# Settings for a test environment which is as close to production as possible.

from .production import *



DEBUG = True

# E-mail address that error messages come from.
SERVER_EMAIL = 'noreply_staging@coralnet.ucsd.edu'

# Default email address to use for various automated correspondence
# from the site manager(s).
DEFAULT_FROM_EMAIL = SERVER_EMAIL

# Subject-line prefix for email messages sent with
# django.core.mail.mail_admins or django.core.mail.mail_managers.
# You'll probably want to include the trailing space.
EMAIL_SUBJECT_PREFIX = '[CoralNet staging] '
