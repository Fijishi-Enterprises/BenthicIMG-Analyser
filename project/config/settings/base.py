# Base settings for any type of server.

import json, sys, os

from unipath import Path

# Normally you should not import ANYTHING from Django directly
# into your settings, but ImproperlyConfigured is an exception.
from django.core.exceptions import ImproperlyConfigured

from .vision_backend import *


# Directory with settings files.
# __file__ is a special Python variable containing the current file's path,
# so we calculate from there.
SETTINGS_DIR = Path(__file__).ancestor(1)

# Base directory of the Django project.
PROJECT_DIR = SETTINGS_DIR.ancestor(2)

# Directory for any site related files, not just the repository.
SITE_DIR = PROJECT_DIR.ancestor(2)

# Directory containing log files
LOG_DIR = SITE_DIR.child('log')

# JSON-based secrets module, expected to be in the SETTINGS_DIR
with open(SETTINGS_DIR.child('secrets.json')) as f:
    secrets = json.loads(f.read())
    def get_secret(setting, secrets=secrets, required=True):
        """
        Get the secret variable. If the variable is required,
        raise an error if it's not present.
        """
        try:
            return secrets[setting]
        except KeyError:
            if required:
                error_msg = "Set the {0} setting in secrets.json".format(setting)
                raise ImproperlyConfigured(error_msg)
            return ""



# In general, first come Django settings, then 3rd-party app settings,
# then our own custom settings.
#
# The Django settings' comments are mainly from
# django.conf.global_settings. (Not all Django settings are there though...)



# If you set this to True, Django will use timezone-aware datetimes.
USE_TZ = True

# Local time zone for this installation. All choices can be found here:
# http://en.wikipedia.org/wiki/List_of_tz_zones_by_name (although not all
# systems may support all possibilities). When USE_TZ is True, this is
# interpreted as the default user time zone.
#
# The value in this base settings module should match what we want for the
# production server. Each developer's settings module can override this
# as needed.
TIME_ZONE = 'America/Los_Angeles'

# Language code for this installation. All choices can be found here:
# http://www.i18nguy.com/unicode/language-identifiers.html
LANGUAGE_CODE = 'en-us'

# Supported languages for text translation.
# 'en' includes sublanguages like 'en-us'.
LANGUAGES = [
    ('en', 'English'),
]

# If you set this to False, Django will make some optimizations so as not
# to load the internationalization machinery.
USE_I18N = False

# If you set this to True, Django will format dates, numbers and calendars
# according to user current locale.
USE_L10N = True

# People who get code error notifications.
# In the format [('Full Name', 'email@example.com'),
# ('Full Name', 'anotheremail@example.com')]
#
# This might be a candidate for the secrets file, but it's borderline;
# it's tied to the admins instead of to the server setup, and it's not that
# much of a secret.
# It's also slightly messier to define a complex setting like this in JSON.
ADMINS = [
    ('Stephen', 'stephenjchan@gmail.com'),
    ('Oscar', 'oscar.beijbom@gmail.com'),
    ('CoralNet', 'coralnet@eng.ucsd.edu'),
]

# Not-necessarily-technical managers of the site. They get broken link
# notifications and other various emails.
MANAGERS = ADMINS

# E-mail address that error messages come from.
SERVER_EMAIL = 'noreply@coralnet.ucsd.edu'

# Default email address to use for various automated correspondence
# from the site manager(s).
DEFAULT_FROM_EMAIL = SERVER_EMAIL

# [Custom setting]
# Email of the labelset-committee group.
LABELSET_COMMITTEE_EMAIL = 'coralnet-labelset@googlegroups.com'

# Subject-line prefix for email messages sent with
# django.core.mail.mail_admins or django.core.mail.mail_managers.
# You'll probably want to include the trailing space.
EMAIL_SUBJECT_PREFIX = '[CoralNet] '

# Database connection info.
DATABASES = {
    'default': {
        # 'postgresql', 'mysql', 'sqlite3' or 'oracle'.
        'ENGINE': 'django.db.backends.postgresql',
        # If True, wraps each request (view function) in a transaction by
        # default. Individual view functions can override this behavior with
        # the non_atomic_requests decorator.
        'ATOMIC_REQUESTS': True,
    }
}

# A list of strings designating all applications that are enabled in this
# Django installation.
#
# When several applications provide different versions of the same resource
# (template, static file, management command, translation), the application
# listed first in INSTALLED_APPS has precedence.
# We do have cases where we want to override default templates with our own
# (e.g. auth and registration pages), so we'll put our apps first.
#
# If an app has an application configuration class, specify the dotted path
# to that class here, rather than just specifying the app package.
INSTALLED_APPS = [
    'accounts',
    'annotations',
    'async_media',
    'bug_reporting',
    # Saves internal server error messages for viewing in the admin site
    'errorlogs.apps.ErrorlogsConfig',
    'export',
    'images',
    'labels',
    # Miscellaneous stuff
    'lib',
    'upload',
    'visualization',
    'vision_backend',

    # Admin site (<domain>/admin)
    'django.contrib.admin',
    # Admin documentation
    'django.contrib.admindocs',
    # User authentication framework
    # https://docs.djangoproject.com/en/dev/topics/auth/
    'django.contrib.auth',
    # Allows permissions to be associated with models you create
    'django.contrib.contenttypes',
    'django.contrib.messages',
    'django.contrib.sessions',
    'django.contrib.staticfiles',

    'easy_thumbnails',
    'guardian',
    'reversion',
    'storages',
]

# The order of middleware classes is important!
# https://docs.djangoproject.com/en/dev/topics/http/middleware/
MIDDLEWARE = [
    'django.middleware.common.CommonMiddleware',
    # Manages sessions across requests; required for auth
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.locale.LocaleMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    # Clickjacking protection
    # https://docs.djangoproject.com/en/dev/ref/clickjacking/
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    # Associates users with requests across sessions; required for auth
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',

    # django-reversion
    'reversion.middleware.RevisionMiddleware',
]

AUTHENTICATION_BACKENDS = [
    # Our subclass of Django's default backend.
    # Allows sign-in by username or email.
    'accounts.auth_backends.UsernameOrEmailModelBackend',
    # django-guardian's backend for per-object permissions.
    # Should be fine to put either before or after the main backend.
    # https://django-guardian.readthedocs.io/en/stable/configuration.html
    'guardian.backends.ObjectPermissionBackend',
]

CACHES = {
    'default': {
        # The default local-memory cache backend is saved per-process, which
        # doesn't cut it if we have more than one server process, e.g.
        # multiple gunicorn worker processes.
        #
        # For example, async media loading uses the cache as a kind of
        # persistent storage between requests. In general, the subsequent
        # requests may be handled by different worker processes, so per-process
        # caches won't work; the cache must be shared between processes.
        'BACKEND': 'django.core.cache.backends.filebased.FileBasedCache',
        'LOCATION': SITE_DIR.child('tmp').child('django_cache'),
        'OPTIONS': {
            # This should at least support:
            # - Label popularities: assume we're always caching 1 entry per
            #   label, for the label list
            # - Async thumbnail requests: however many might be generated in
            #   the expiration duration
            'MAX_ENTRIES': 10000,
        }
    }
}

ROOT_URLCONF = 'config.urls'

# A list containing the settings for all template engines to be used
# with Django. Each item of the list is a dictionary containing the
# options for an individual engine.
# https://docs.djangoproject.com/en/dev/ref/settings/#templates
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [
            PROJECT_DIR.child('templates'),
        ],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                # Adds current user and permissions to the template context.
                'django.contrib.auth.context_processors.auth',
                'django.template.context_processors.debug',
                'django.template.context_processors.i18n',
                'django.template.context_processors.media',
                # Adds 'request' (current HttpRequest) to the context.
                # Not included by default as of Django 1.8.
                'django.template.context_processors.request',
                'django.template.context_processors.static',
                'django.template.context_processors.tz',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

# A list of locations of additional static files
# (besides apps' "static/" subdirectories, which are automatically included)
STATICFILES_DIRS = [
    # Project-wide static files
    PROJECT_DIR.child('static'),
]

# The default file storage backend used during the build process.
# ManifestStaticFilesStorage appends a content-based hash to the filename
# to facilitate browser caching.
# This hash appending happens as a post-processing step in collectstatic, so
# it only applies to DEBUG False.
# https://docs.djangoproject.com/en/dev/ref/contrib/staticfiles/#manifeststaticfilesstorage
STATICFILES_STORAGE = \
    'django.contrib.staticfiles.storage.ManifestStaticFilesStorage'

# List of finder classes that know how to find static files in
# various locations.
STATICFILES_FINDERS = [
    'django.contrib.staticfiles.finders.FileSystemFinder',
    'django.contrib.staticfiles.finders.AppDirectoriesFinder',
#    'django.contrib.staticfiles.finders.DefaultStorageFinder',
]

# Absolute path to the directory which static files should be collected to.
# Example: "/home/media/media.lawrence.com/static/"
#
# To collect static files in STATIC_ROOT, first ensure that your static files
# are in apps' "static/" subdirectories and in STATICFILES_DIRS. Then use the
# collectstatic management command.
# Don't put anything in STATIC_ROOT manually.
#
# Then, use your web server's settings (e.g. nginx, Apache) to serve
# STATIC_ROOT at the STATIC_URL.
# This is done outside of Django, but the docs have some implementation
# suggestions. Basically, you either serve directly from the STATIC_ROOT
# with nginx, or you push the STATIC_ROOT to a separate static-file server
# and serve from there.
# https://docs.djangoproject.com/en/dev/howto/static-files/deployment/
#
# This only is used when DEBUG = False. When DEBUG = True, static files
# are served automagically with django.contrib.staticfiles.views.serve().
#
# Regardless of DEBUG, as long as we're using ManifestStaticFilesStorage,
# this setting is required. Otherwise, Django gets an
# ImproperlyConfiguredError. So, even devs need this value set to something.
STATIC_ROOT = SITE_DIR.child('static_serve')

# URL that handles the static files served from STATIC_ROOT.
# (Or, if DEBUG is True, served automagically with the static-serve view.)
# Example: "http://media.lawrence.com/static/"
STATIC_URL = '/static/'

# Don't expire the sign-in session when the user closes their browser
# (Unless set_expiry(0) is explicitly called on the session).
SESSION_EXPIRE_AT_BROWSER_CLOSE = False
# The age of session cookies, in seconds.
SESSION_COOKIE_AGE = 60 * 60 * 24 * 30

# A secret key for this particular Django installation. Used in secret-key
# hashing algorithms.
# Make this unique. Django's manage.py startproject command automatically
# generates a random secret key and puts it in settings, so use that.
SECRET_KEY = get_secret("DJANGO_SECRET_KEY")

LOGIN_URL = 'auth_login'
LOGIN_REDIRECT_URL = 'source_list'

# Custom setting.
MINIMUM_PASSWORD_LENGTH = 10
# Built-in setting.
# The list of validators that are used to check the strength of user passwords.
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {
            'min_length': MINIMUM_PASSWORD_LENGTH,
        }
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.PBKDF2PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher',
    # This hasher assists in strengthening security for users who haven't
    # logged in since PBKDF2 became the default.
    'accounts.hashers.PBKDF2WrappedSHA1PasswordHasher',
    'django.contrib.auth.hashers.Argon2PasswordHasher',
    'django.contrib.auth.hashers.BCryptSHA256PasswordHasher',
]

# The maximum size (in bytes) that an upload will be before it
# gets streamed to the file system.
#
# The value in this base settings module should match what we want for the
# production server. Each developer's settings module can override this
# as needed.
FILE_UPLOAD_MAX_MEMORY_SIZE = 52428800  # 50 MB



# django-registration setting
# The number of days users will have to activate their accounts after
# registering. If a user does not activate within that period,
# the account will remain permanently inactive
# unless a site administrator manually activates it.
ACCOUNT_ACTIVATION_DAYS = 7

# [Custom setting]
# The number of hours users will have to confirm an email change after
# requesting one.
EMAIL_CHANGE_CONFIRMATION_HOURS = 24



# [Custom settings]
# Media filepath patterns
IMAGE_FILE_PATTERN = 'images/{name}{extension}'
LABEL_THUMBNAIL_FILE_PATTERN = 'labels/{name}{extension}'
POINT_PATCH_FILE_PATTERN = \
    '{full_image_path}.pointpk{point_pk}.thumbnail.jpg'
PROFILE_AVATAR_FILE_PATTERN = 'avatars/{name}{extension}'

# [Custom setting]
MAINTENANCE_STATUS_FILE_PATH = SITE_DIR.child('tmp').child('maintenance.json')

# [Custom settings] Special users
IMPORTED_USERNAME = "Imported"
ROBOT_USERNAME = "robot"
ALLEVIATE_USERNAME = "Alleviate"

# [Custom settings] Upload restrictions
IMAGE_UPLOAD_MAX_FILE_SIZE = 30*1024*1024  # 30 MB
IMAGE_UPLOAD_MAX_DIMENSIONS = (8000, 8000)
IMAGE_UPLOAD_ACCEPTED_CONTENT_TYPES = [
    # https://www.sitepoint.com/web-foundations/mime-types-complete-list/
    'image/jpeg',
    'image/pjpeg',  # Progressive JPEG
    'image/png',
    'image/mpo',
]
CSV_UPLOAD_MAX_FILE_SIZE = 30*1024*1024  # 30 MB

# [Custom settings]
BROWSE_DEFAULT_THUMBNAILS_PER_PAGE = 20

# [Custom setting]
# Image counts required for sources to: display on the map,
# display as medium size, and display as large size.
MAP_IMAGE_COUNT_TIERS = [100, 500, 1500]

# [Custom setting]
# https://developers.google.com/maps/faq - "How do I get a new API key?"
# It seems that development servers don't need an API key though.
GOOGLE_MAPS_API_KEY = get_secret("GOOGLE_MAPS_API_KEY", required=False)

# [Custom settings]
GOOGLE_ANALYTICS_CODE = get_secret("GOOGLE_ANALYTICS_CODE", required=False)

# Celery
BROKER_URL = 'redis://localhost:6379'
BROKER_TRANSPORT = 'redis'
CELERYD_CONCURRENCY = 2
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'

# LOG
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'standard': {
            'format': '[%(name)s.%(funcName)s, %(asctime)s]: %(message)s'
        },
    },
    'handlers': {
        'backend': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': LOG_DIR.child('vision_backend.log'),
            'formatter': 'standard'
        },
        'backend_debug': {
            'level': 'DEBUG',
            'class': 'logging.FileHandler',
            'filename': LOG_DIR.child('vision_backend_debug.log'),
            'formatter': 'standard'
        },
    },
    'loggers': {
        'vision_backend': {
            'handlers': ['backend', 'backend_debug'],
            'level': 'DEBUG',
            'propagate': True,
        }
    },

}

# [Custom setting]
# Name of the CoralNet regtests S3 bucket.
REGTEST_BUCKET = 'coralnet-regtest-fixtures'

# [Custom setting]
# Browsers to run Selenium tests in.
# This is a list of dicts. Each dict supports the following keys:
#
# name
#   (Required) Name of the browser. Not case sensitive.
#   Supported: 'Firefox', 'Chrome', 'PhantomJS'.
# webdriver
#   Absolute path to the web driver program, such as geckodriver.exe for
#   Firefox on Windows. If not specified, it searches your PATH for the
#   web driver.
#   For PhantomJS, this is the phantomjs executable.
# browser_binary
#   Absolute path to the browser binary, such as firefox.exe for Firefox
#   on Windows. If not specified, it looks on your PATH or your Windows
#   registry.
#   Only applies to Firefox.
#
# For now, only ONE browser is picked: the first one listed in this setting.
# Running in multiple browsers will hopefully be implemented in the future
# (with test parametrization or something).
#
# Note that PhantomJS seems to need the Selenium server / remote webdriver,
# and so needs extra setup steps to work:
# http://selenium-python.readthedocs.io/installation.html#downloading-selenium-server
# https://github.com/detro/ghostdriver#register-ghostdriver-with-a-selenium-grid-hub
SELENIUM_BROWSERS = [{'name': 'Firefox'}, {'name': 'Chrome'}]

# [Custom setting]
# Timeouts for Selenium tests, in seconds.
SELENIUM_TIMEOUTS = {
    'short': 0.5,
    'medium': 5,
    # Hard wait time after a DB-changing operation to ensure consistency.
    # Without this wait time, we may get odd effects such as the DB not getting
    # rolled back before starting the next test.
    'db_consistency': 0.5,
    # Timeout when waiting for a page to load. If the page loads beforehand,
    # the timeout's cut short. If the page doesn't load within this time, we
    # get an error.
    'page_load': 20,
}

# We filter on sources that contains these strings for map and some exports.
LIKELY_TEST_SOURCE_NAMES = ['test', 'sandbox', 'dummy', 'tmp', 'temp', 'check']
