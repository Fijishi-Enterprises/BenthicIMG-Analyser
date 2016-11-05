# Partial settings definition for setups using local file storage.
# Note that the MEDIA_URL definition assumes DEBUG is True.

from .base import get_secret, SITE_DIR, DATABASES



DATABASES['default'].update({
    # Database name, or path to database file if using sqlite3.
    'NAME': get_secret("LOCAL_STORAGE_DATABASE_NAME"),
    # Not used with sqlite3.
    'USER': get_secret("LOCAL_STORAGE_DATABASE_USER"),
    # Not used with sqlite3.
    'PASSWORD': get_secret("LOCAL_STORAGE_DATABASE_PASSWORD", required=False),
    # Set to empty string for localhost. Not used with sqlite3.
    'HOST': get_secret("LOCAL_STORAGE_DATABASE_HOST", required=False),
    # Set to empty string for default. Not used with sqlite3.
    'PORT': get_secret("LOCAL_STORAGE_DATABASE_PORT", required=False),
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
