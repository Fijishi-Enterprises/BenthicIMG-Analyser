# Pick one.

from .local import *
# from .staging import *

# Easier to run fakeemail here than on the default SMTP port of 25
# (which would require root privileges)
EMAIL_PORT = 2025
