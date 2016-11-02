# Partial settings definition for setups using Amazon S3.

from .base import get_secret, DATABASES



DATABASES['default'].update({
    # Database name, or path to database file if using sqlite3.
    'NAME': get_secret("DATABASE_NAME"),
    # Not used with sqlite3.
    'USER': get_secret("DATABASE_USER"),
    # Not used with sqlite3.
    'PASSWORD': get_secret("DATABASE_PASSWORD"),
    # Set to empty string for localhost. Not used with sqlite3.
    'HOST': get_secret("DATABASE_HOST"),
    # Set to empty string for default. Not used with sqlite3.
    'PORT': get_secret("DATABASE_PORT"),
})

# django-storages settings
# http://django-storages.readthedocs.io/en/latest/backends/amazon-S3.html
AWS_ACCESS_KEY_ID = get_secret('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = get_secret('AWS_SECRET_ACCESS_KEY')
AWS_STORAGE_BUCKET_NAME = get_secret('AWS_STORAGE_BUCKET_NAME')
# Default ACL permissions when saving S3 files.
# 'private' means the bucket-owning AWS account has full permissions, and no
# one else has permissions. Further permissions can be specified in the bucket
# policy or in the IAM console.
AWS_DEFAULT_ACL = 'private'

# Default file storage mechanism that holds media.
DEFAULT_FILE_STORAGE = 'lib.storage_backends.MediaStorageS3'

# easy_thumbnails setting
# Default file storage for saving generated thumbnails.
#
# The only downside of not using the app's provided storage class is that
# the THUMBNAIL_MEDIA_ROOT and THUMBNAIL_MEDIA_URL settings won't work
# (we'd have to apply them manually). We aren't using these settings, though.
THUMBNAIL_DEFAULT_STORAGE = DEFAULT_FILE_STORAGE

# [Custom settings]
# S3 details on storing media.
AWS_S3_DOMAIN = 's3-us-west-2.amazonaws.com/{bucket_name}'.format(
    bucket_name=AWS_STORAGE_BUCKET_NAME)
AWS_S3_MEDIA_SUBDIR = 'media'

# Base URL where user-uploaded media are served.
# Example: "http://media.lawrence.com/media/"
MEDIA_URL = 'https://{domain}/{subdir}/'.format(
    domain=AWS_S3_DOMAIN, subdir=AWS_S3_MEDIA_SUBDIR)

# django-storages setting
# S3 bucket subdirectory in which to store media.
AWS_LOCATION = AWS_S3_MEDIA_SUBDIR
