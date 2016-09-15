from .local import *

# Use this import instead when testing stuff like S3, but make sure to
# specify different secrets (e.g. S3 bucket) from actual production.
#from .production import *

# Nice to have static files working when testing other production settings.
DEBUG = True

# If running tests, use SQLite to speed up the test runs greatly.
# http://stackoverflow.com/a/3098182
#
# The obvious drawback is that different databases have different behavior,
# and could have different test results. It's happened before.
# So, comment this out to run in PostgreSQL every so often.
DATABASES['default']['ENGINE'] = 'django.db.backends.sqlite3'
DATABASES['default']['NAME'] = 'coralnet_sqlite_database'

AWS_ACCESS_KEY_ID = get_secret('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = get_secret('AWS_SECRET_ACCESS_KEY')
AWS_STORAGE_BUCKET_NAME = 'coralnet-beijbom-dev'

# Default file storage mechanism that holds media.
DEFAULT_FILE_STORAGE = 'lib.storage_backends.MediaStorageS3'

AWS_S3_DOMAIN = 's3-us-west-2.amazonaws.com/{bucket_name}'.format(
    bucket_name=AWS_STORAGE_BUCKET_NAME)
AWS_S3_MEDIA_SUBDIR = 'media'

MEDIA_URL = 'https://{domain}/{subdir}/'.format(
    domain=AWS_S3_DOMAIN, subdir=AWS_S3_MEDIA_SUBDIR)

AWS_LOCATION = AWS_S3_MEDIA_SUBDIR
