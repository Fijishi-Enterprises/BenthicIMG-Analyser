# Settings to be used for continuous integration (e.g. GitHub Actions).
# Here we don't use secrets.json since these settings are just for testing

from .base_devserver import *


DATABASES['default'].update({
    # Database name.
    'NAME': 'postgres',
    # Username and password.
    'USER': 'postgres',
    'PASSWORD': 'postgres',
    # Set to empty string for localhost.
    'HOST': 'localhost',
    # Set to empty string for default.
    'PORT': 5432,
})

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
# This setting only applies when such files are saved to a filesystem path,
# not when they are uploaded to a cloud service like AWS.
MEDIA_ROOT = SITE_DIR.child('media')

# Base URL where user-uploaded media are served.
#
# Here we assume DEBUG is True, in which case this should be a relative URL.
# Django will serve the contents of MEDIA_ROOT there.
# The code that does the serving is in the root urlconf.
MEDIA_URL = '/media/'
