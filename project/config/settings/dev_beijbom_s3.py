from .base_devserver import *
from .storage_s3 import *

# If running tests, use SQLite to speed up the test runs greatly.
# http://stackoverflow.com/a/3098182
#
# The obvious drawback is that different databases have different behavior,
# and could have different test results. It's happened before.
# So, comment this out to run in PostgreSQL every so often.
# DATABASES['default']['ENGINE'] = 'django.db.backends.sqlite3'
# DATABASES['default']['NAME'] = 'coralnet_sqlite_database'
