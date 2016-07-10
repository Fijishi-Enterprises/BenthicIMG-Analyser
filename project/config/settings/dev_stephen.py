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
# if 'test' in sys.argv:
#     DATABASES['default']['ENGINE'] = 'django.db.backends.sqlite3'