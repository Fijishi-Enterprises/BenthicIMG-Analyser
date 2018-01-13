from .base_devserver import *

# Pick one.
from .storage_local import *
# from .storage_s3 import *
# from .storage_regtests import *

MAP_IMAGE_COUNT_TIERS = [5, 20, 50]

MIN_NBR_ANNOTATED_IMAGES = 5

# If I ever test with DEBUG = False, I'll want to:
# - Set an ALLOWED_HOSTS, otherwise runserver gets a CommandError
# - Set a STATIC_URL which I can serve static files to,
#   say using `python -m http.server 8080` (this syntax is Python 3),
#   and remember to use the collectstatic command
# - Set a MEDIA_URL which I can serve media files to,
#   say using `python -m http.server 8070`
#
# But I'll leave these all commented out if DEBUG = True, because it's easier
# to not bother with starting up those extra servers, and ALLOWED_HOSTS gets
# intelligently filled in if DEBUG = True:
# https://docs.djangoproject.com/en/dev/ref/settings/#allowed-hosts
#DEBUG = False
#ALLOWED_HOSTS = ['*']
#MEDIA_URL = 'http://127.0.0.1:8070/'
#STATIC_URL = 'http://127.0.0.1:8080/'
