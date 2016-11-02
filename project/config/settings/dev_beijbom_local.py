from .base_devserver import *
from .storage_local import *

DEBUG = True

DATABASES['default']['ENGINE'] = 'django.db.backends.sqlite3'
DATABASES['default']['NAME'] = 'coralnet_sqlite_database'
