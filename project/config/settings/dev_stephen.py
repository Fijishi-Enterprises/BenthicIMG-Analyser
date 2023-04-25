import sys

from .base_devserver import *

# Pick one.
from .storage_local import *
# from .storage_s3 import *

# Use this if you're not using AWS. Or if you just want feature extraction to
# be faster.
FORCE_DUMMY_EXTRACTOR = True

# By default, huey runs tasks immediately if DEBUG is True, and doesn't if
# False. Can override that behavior here.
# HUEY['immediate'] = False

# Needed for regtests and BatchQueue.
AWS_ACCESS_KEY_ID = get_secret('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = get_secret('AWS_SECRET_ACCESS_KEY')
os.environ['SPACER_AWS_ACCESS_KEY_ID'] = AWS_ACCESS_KEY_ID
os.environ['SPACER_AWS_SECRET_ACCESS_KEY'] = AWS_SECRET_ACCESS_KEY

# Option for regtests. BatchQueue needs storage_s3 as well.
# SPACER_QUEUE_CHOICE = 'vision_backend.queues.BatchQueue'

MAP_IMAGE_COUNT_TIERS = [5, 20, 50]

MIN_NBR_ANNOTATED_IMAGES = 5

# For now, only the first specified browser gets used for Selenium tests.
SELENIUM_BROWSERS = [
    # Headless Chrome
    {
        'name': 'Chrome',
        'webdriver': r'C:\Programs_non_installed\Webdrivers\chromedriver.exe',
        'options': ['--headless'],
    },
    # Headless Firefox
    {
        'name': 'Firefox',
        'webdriver': r'C:\Programs_non_installed\Webdrivers\geckodriver.exe',
        'browser_binary': r'C:\Programs_non_installed\FirefoxPortable\S\App\firefox64\firefox.exe',
        'options': ['-headless'],
    },
    # Regular Chrome
    {
        'name': 'Chrome',
        'webdriver': r'C:\Programs_non_installed\Webdrivers\chromedriver.exe',
    },
    # Regular Firefox
    {
        'name': 'Firefox',
        'webdriver': r'C:\Programs_non_installed\Webdrivers\geckodriver.exe',
        'browser_binary': r'C:\Programs_non_installed\FirefoxPortable\S\App\firefox64\firefox.exe',
    },
]

# I'll uncomment this for running our Selenium tests, since those tests
# require an in-memory database like SQLite.
#if 'test' in sys.argv:
#    DATABASES['default']['ENGINE'] = 'django.db.backends.sqlite3'

# If I ever test with DEBUG = False, I'll want to:
# - Set a STATIC_URL which I can serve static files to,
#   say using `python -m http.server 8080` (this syntax is Python 3),
#   and remember to use the collectstatic command
# - Set a MEDIA_URL which I can serve media files to,
#   say using `python -m http.server 8070` or using this way with CORS:
#   https://stackoverflow.com/questions/21956683/
#
# But I'll leave these all commented out if DEBUG = True, because it's easier
# to not bother with starting up those extra servers.
#DEBUG = False
#MEDIA_URL = 'http://localhost:8070/'
#STATIC_URL = 'http://127.0.0.1:8080/'

CAROUSEL_IMAGE_COUNT = 2
CAROUSEL_IMAGE_POOL = [
    516, 515, 514
]

# # Log all database queries.
# LOGGING['handlers']['database'] = {
#     'filename': LOG_DIR.child('database.log'),
#     'class': 'logging.FileHandler',
#     'level': 'DEBUG',
#     'formatter': 'standard',
# }
# LOGGING['loggers']['django.db.backends'] = {
#     'handlers': ['database'],
#     'level': 'DEBUG',
#     'propagate': True,
# }
