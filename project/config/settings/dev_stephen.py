# Pick one.

from .local import *
# from .staging import *

# Instead of routing emails through a mail server,
# just print emails to the console
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
