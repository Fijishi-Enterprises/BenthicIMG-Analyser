from .local import *

# If running tests, use SQLite to speed up the test runs greatly.
# http://stackoverflow.com/a/3098182
#
# The obvious drawback is that different databases have different behavior,
# and could have different test results. It's happened before.
# So, comment this out to run in PostgreSQL every so often.
if ('test' in sys.argv or 'mytest' in sys.argv):
    DATABASES['default']['ENGINE'] = 'django.db.backends.sqlite3'