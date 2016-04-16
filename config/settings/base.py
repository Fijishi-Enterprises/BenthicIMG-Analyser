import json, sys

from unipath import Path

# Normally you should not import ANYTHING from Django directly
# into your settings, but ImproperlyConfigured is an exception.
from django.core.exceptions import ImproperlyConfigured



# Directory with settings files.
# __file__ is a special Python variable containing the current file's path,
# so we calculate from there.
SETTINGS_DIR = Path(__file__).ancestor(1)

# Base directory of the version control project.
PROJECT_DIR = SETTINGS_DIR.ancestor(2)

# JSON-based secrets module, expected to be in the SETTINGS_DIR
with open(SETTINGS_DIR.child('secrets.json')) as f:
    secrets = json.loads(f.read())
    def get_secret(setting, secrets=secrets):
        """Get the secret variable or return explicit exception."""
        try:
            return secrets[setting]
        except KeyError:
            error_msg = "Set the {0} setting in secrets.json".format(setting)
            raise ImproperlyConfigured(error_msg)



# First come Django settings, then 3rd-party app settings,
# then our own custom settings.
#
# The Django settings' comments and ordering are mainly from
# django.conf.global_settings. (Not all Django settings are there though...)



# If this is True, the fancy error page will display a
# detailed report for any exception raised during template rendering.
# This report contains the relevant snippet of the template,
# with the appropriate line highlighted.
# Note that Django only displays fancy error pages if DEBUG is True,
# so you'll want to set that to take advantage of this setting.
TEMPLATE_DEBUG = True

# If you set this to True, Django will use timezone-aware datetimes.
USE_TZ = True

# Language code for this installation. All choices can be found here:
# http://www.i18nguy.com/unicode/language-identifiers.html
LANGUAGE_CODE = 'en-us'

# Part of Django's sites framework.
SITE_ID = 1

# If you set this to False, Django will make some optimizations so as not
# to load the internationalization machinery.
USE_I18N = True

# If you set this to True, Django will format dates, numbers and calendars
# according to user current locale.
USE_L10N = True

# E-mail address that error messages come from.
SERVER_EMAIL = 'noreply@coralnet.ucsd.edu'

# Database connection info.
DATABASES = {
    'default': {
        # 'postgresql_psycopg2', 'mysql', 'sqlite3' or 'oracle'.
        'ENGINE': 'django.db.backends.postgresql_psycopg2',
        # Or path to database file if using sqlite3.
        'NAME': 'coralnet',
        # Not used with sqlite3.
        'USER': 'django',
        # Not used with sqlite3.
        'PASSWORD': get_secret("DATABASES_PASSWORD"),
        # Set to empty string for localhost. Not used with sqlite3.
        'HOST': get_secret("DATABASES_HOST"),
        # Set to empty string for default. Not used with sqlite3.
        'PORT': get_secret("DATABASES_PORT"),
        # If True, wraps each request (view function) in a transaction by
        # default. Individual view functions can override this behavior with
        # the non_atomic_requests decorator.
        'ATOMIC_REQUESTS': True,
    }
}
# If running tests, use SQLite. Two reasons:
# (1) Our empty labelset ID is -1. When this isn't a positive number,
#     test startup with PostgreSQL dies with a DatabaseError: "value -1 is
#     out of bounds for sequence ...". This doesn't happen with SQLite.
# (2) The SQLite test database is entirely in memory, speeding up the test
#     runs greatly. http://stackoverflow.com/a/3098182
#
# The obvious drawback is that different databases have different behavior,
# and could have different test results. It's happened before.
# Once the empty labelset ID thing is fixed, this should be just PostgreSQL
# in base.py, and one could specify SQLite for tests in a dev_<name>.py file.
if ('test' in sys.argv or 'mytest' in sys.argv):
    DATABASES['default']['ENGINE'] = 'django.db.backends.sqlite3'

# Define our project's installed apps separately from built-in and
# third-party installed apps. This'll make it easier to define a
# custom test command that only runs our apps' tests.
# http://stackoverflow.com/a/2329425/
PROJECT_APPS = [
    'accounts',
    'images',
    'upload',
    'annotations',
    'visualization',
    'bug_reporting',
    'requests',
    'map',
    'lib',
]
REQUIRED_APPS = [
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.sites',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # Uncomment the next line to enable the admin:
    'django.contrib.admin',
    # Uncomment the next line to enable admin documentation:
    'django.contrib.admindocs',
    'userena',
    'userena.contrib.umessages',
    'guardian',
    'easy_thumbnails',
    'reversion',
]
INSTALLED_APPS = REQUIRED_APPS + PROJECT_APPS

ROOT_URLCONF = 'config.urls'

# List of locations of the template source files, in search order.
TEMPLATE_DIRS = (
    PROJECT_DIR.child('templates'),
)

# List of callables that know how to import templates from various sources.
# See the comments in django/core/template/loader.py for interface
# documentation.
TEMPLATE_LOADERS = (
    'django.template.loaders.filesystem.Loader',
    'django.template.loaders.app_directories.Loader',
    'django.template.loaders.eggs.Loader',
)

# List of processors used by RequestContext to populate the context.
# Each one should be a callable that takes the request object as its
# only parameter and returns a dictionary to add to the context.
TEMPLATE_CONTEXT_PROCESSORS = (
    "django.contrib.auth.context_processors.auth",
    "django.core.context_processors.debug",
    "django.core.context_processors.i18n",
    "django.core.context_processors.media",
    "django.core.context_processors.static",
    "django.contrib.messages.context_processors.messages",
    "django.core.context_processors.request",
)

# Default email address to use for various automated correspondence
# from the site manager(s).
DEFAULT_FROM_EMAIL = SERVER_EMAIL

# Subject-line prefix for email messages sent with
# django.core.mail.mail_admins or django.core.mail.mail_managers.
# You'll probably want to include the trailing space.
EMAIL_SUBJECT_PREFIX = '[CoralNet] '

# A secret key for this particular Django installation. Used in secret-key
# hashing algorithms.
# Make this unique. Django's manage.py startproject command automatically
# generates a random secret key and puts it in settings, so use that.
SECRET_KEY = get_secret("SECRET_KEY")

# Absolute filesystem path to the directory that will hold user-uploaded files.
# Example: "/home/media/media.lawrence.com/media/"
#
# TODO: Get this directory out of version control. In general it should
# be not only out of the project directory, but also a location that'd be
# defined differently between local and production.
MEDIA_ROOT = PROJECT_DIR.child('media')

# URL that handles the media served from MEDIA_ROOT.
# Example: "http://media.lawrence.com/media/"
MEDIA_URL = '/media/'

# URL that handles the static files served from STATIC_ROOT.
# Example: "http://media.lawrence.com/static/"
STATIC_URL = '/static/'

# The order of middleware classes is important!
# https://docs.djangoproject.com/en/dev/topics/http/middleware/
MIDDLEWARE_CLASSES = (
    'django.middleware.common.CommonMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.locale.LocaleMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    # Clickjacking protection
    # https://docs.djangoproject.com/en/dev/ref/clickjacking/
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',

    # django-userena
    'userena.middleware.UserenaLocaleMiddleware',
    # django-reversion
    'reversion.middleware.RevisionMiddleware',
)

AUTHENTICATION_BACKENDS = (
    'userena.backends.UserenaAuthenticationBackend',
    'guardian.backends.ObjectPermissionBackend',
    # This one is in Django's default setting
    'django.contrib.auth.backends.ModelBackend',
)

LOGIN_URL = '/accounts/signin/'
LOGOUT_URL = '/accounts/signout/'
LOGIN_REDIRECT_URL = '/images/source/'

# The name of the class to use to run the test suite
TEST_RUNNER = 'lib.test_utils.MyTestSuiteRunner'

# A list of locations of additional static files
# (besides apps' "static/" subdirectories, which are automatically included)
#
# Remember that a 1-element tuple like ('item',) needs a comma before
# the right parenthesis.
STATICFILES_DIRS = (
    # Project-wide static files
    PROJECT_DIR.child('static'),
)

# List of finder classes that know how to find static files in
# various locations.
STATICFILES_FINDERS = (
    'django.contrib.staticfiles.finders.FileSystemFinder',
    'django.contrib.staticfiles.finders.AppDirectoriesFinder',
#    'django.contrib.staticfiles.finders.DefaultStorageFinder',
)



# django-guardian setting
ANONYMOUS_USER_ID = -1
# For whatever reason, when running tests in Postgres, it errors when
# this ID is 0 or negative.
if 'test' in sys.argv or 'mytest' in sys.argv:
    ANONYMOUS_USER_ID = 99999999



# django-userena settings
AUTH_PROFILE_MODULE = 'accounts.Profile'
USERENA_SIGNIN_REDIRECT_URL = LOGIN_REDIRECT_URL
USERENA_USE_MESSAGES = False
USERENA_LANGUAGE_FIELD = 'en'

# TODO: Honestly no idea if this is still needed (or what it does)
USERENA_MODULE_PATH = PROJECT_DIR.ancestor(1)
sys.path.insert(0, USERENA_MODULE_PATH)



# RabbitMQ settings
BROKER_HOST = get_secret("RABBITMQ_HOST")
BROKER_PORT = get_secret("RABBITMQ_PORT")
BROKER_USER = "coralnet"
BROKER_PASSWORD = get_secret("RABBITMQ_PASSWORD")
BROKER_VHOST = get_secret("RABBITMQ_VHOST")



# [Custom setting]
# Directory containing uploadable files for use during unit tests.
SAMPLE_UPLOADABLES_ROOT = PROJECT_DIR.child('sample_uploadables')

# [Custom settings]
# File uploading
ORIGINAL_IMAGE_DIR = 'data/original/'
LABEL_THUMBNAIL_DIR = 'label_thumbnails/'

# [Custom settings] Special user ids
# (Be sure not to collide with django-guardian's special user id)
IMPORTED_USER_ID = -2
ROBOT_USER_ID = -3
ALLEVIATE_USER_ID = -4

# [Custom setting]
# Go to https://code.google.com/apis/console/ and get an API key
GOOGLE_MAPS_API_KEY = get_secret("GOOGLE_MAPS_API_KEY")

# [Custom settings]
CAPTCHA_PRIVATE_KEY = get_secret("CAPTCHA_PRIVATE_KEY")
CAPTCHA_PUBLIC_KEY = get_secret("CAPTCHA_PUBLIC_KEY")



# VISION BACKEND SETTINGS
# TODO: move to separate settings file.
NEW_MODEL_THRESHOLD = 1.5
MIN_NBR_ANNOTATED_IMAGES = 5
NBR_IMAGES_PER_LOOP = 100