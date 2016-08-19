import json, sys

from unipath import Path

# Normally you should not import ANYTHING from Django directly
# into your settings, but ImproperlyConfigured is an exception.
from django.core.exceptions import ImproperlyConfigured



# Directory with settings files.
# __file__ is a special Python variable containing the current file's path,
# so we calculate from there.
SETTINGS_DIR = Path(__file__).ancestor(1)

# Base directory of the Django project.
PROJECT_DIR = SETTINGS_DIR.ancestor(2)

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



# First come Django settings, then 3rd-party app settings,
# then our own custom settings.
#
# The Django settings' comments and ordering are mainly from
# django.conf.global_settings. (Not all Django settings are there though...)



# If you set this to True, Django will use timezone-aware datetimes.
USE_TZ = True

# Language code for this installation. All choices can be found here:
# http://www.i18nguy.com/unicode/language-identifiers.html
LANGUAGE_CODE = 'en-us'

# Required if the django.contrib.sites framework is used.
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
        # 'postgresql', 'mysql', 'sqlite3' or 'oracle'.
        'ENGINE': 'django.db.backends.postgresql',
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

# A list of strings designating all applications that are enabled in this
# Django installation.
#
# When several applications provide different versions of the same resource
# (template, static file, management command, translation), the application
# listed first in INSTALLED_APPS has precedence.
#
# If an app has an application configuration class, specify the dotted path
# to that class here, rather than just specifying the app package.
INSTALLED_APPS = [
    # Uncomment the next line to enable the admin:
    'django.contrib.admin',
    # Uncomment the next line to enable admin documentation:
    'django.contrib.admindocs',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.messages',
    'django.contrib.sessions',
    # Required by userena as of 2.0.1, otherwise an import fails...
    'django.contrib.sites',
    'django.contrib.staticfiles',

    'easy_thumbnails',
    'guardian',
    'reversion',
    'storages',
    'userena',
    'userena.contrib.umessages',

    'accounts',
    'annotations',
    'bug_reporting',
    'errorlogs.apps.ErrorlogsConfig',
    'images',
    'lib',
    'requests',
    'upload',
    'visualization',
]

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
                'django.contrib.auth.context_processors.auth',
                'django.template.context_processors.debug',
                'django.template.context_processors.i18n',
                'django.template.context_processors.media',
                # request: Not included by default as of Django 1.8.
                # If this processor is enabled, every RequestContext will
                # contain a variable request, which is the current HttpRequest.
                'django.template.context_processors.request',
                'django.template.context_processors.static',
                'django.template.context_processors.tz',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

# Default email address to use for various automated correspondence
# from the site manager(s).
DEFAULT_FROM_EMAIL = SERVER_EMAIL

# Subject-line prefix for email messages sent with
# django.core.mail.mail_admins or django.core.mail.mail_managers.
# You'll probably want to include the trailing space.
EMAIL_SUBJECT_PREFIX = '[Beta CoralNet] '

# A secret key for this particular Django installation. Used in secret-key
# hashing algorithms.
# Make this unique. Django's manage.py startproject command automatically
# generates a random secret key and puts it in settings, so use that.
SECRET_KEY = get_secret("SECRET_KEY")

# URL that handles the static files served from STATIC_ROOT.
# (Or, if DEBUG is True, served automagically with the static-serve view.)
# Example: "http://media.lawrence.com/static/"
STATIC_URL = '/static/'

# The order of middleware classes is important!
# https://docs.djangoproject.com/en/dev/topics/http/middleware/
MIDDLEWARE_CLASSES = [
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
]

AUTHENTICATION_BACKENDS = [
    'userena.backends.UserenaAuthenticationBackend',
    'guardian.backends.ObjectPermissionBackend',
    # This one is in Django's default setting
    'django.contrib.auth.backends.ModelBackend',
]

LOGIN_URL = '/accounts/signin/'
LOGOUT_URL = '/accounts/signout/'
LOGIN_REDIRECT_URL = '/images/source/'

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

# A list of locations of additional static files
# (besides apps' "static/" subdirectories, which are automatically included)
STATICFILES_DIRS = [
    # Project-wide static files
    PROJECT_DIR.child('static'),
]

# List of finder classes that know how to find static files in
# various locations.
STATICFILES_FINDERS = [
    'django.contrib.staticfiles.finders.FileSystemFinder',
    'django.contrib.staticfiles.finders.AppDirectoriesFinder',
#    'django.contrib.staticfiles.finders.DefaultStorageFinder',
]



# django-guardian setting
ANONYMOUS_USER_ID = -1
# For whatever reason, when running tests in Postgres, it errors when
# this ID is 0 or negative.
if 'test' in sys.argv:
    ANONYMOUS_USER_ID = 99999999



# django-userena settings
AUTH_PROFILE_MODULE = 'accounts.Profile'
USERENA_SIGNIN_REDIRECT_URL = LOGIN_REDIRECT_URL
USERENA_USE_MESSAGES = False
USERENA_LANGUAGE_FIELD = 'en'



# [Custom setting]
# Directory containing uploadable files for use during unit tests.
SAMPLE_UPLOADABLES_ROOT = PROJECT_DIR.child('sample_uploadables')

# [Custom settings]
# Media filepath patterns
IMAGE_FILE_PATTERN = 'images/{name}{extension}'
LABEL_THUMBNAIL_FILE_PATTERN = 'labels/{name}{extension}'
POINT_PATCH_FILE_PATTERN = \
    '{full_image_path}.pointpk{point_pk}.thumbnail.jpg'
FEATURE_VECTOR_FILE_PATTERN = \
    '{full_image_path}.pointpk{point_pk}.featurevector'

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
]
CSV_UPLOAD_MAX_FILE_SIZE = 30*1024*1024  # 30 MB

# [Custom settings]
BROWSE_DEFAULT_THUMBNAILS_PER_PAGE = 20

# [Custom setting]
# Go to https://code.google.com/apis/console/ and get an API key
GOOGLE_MAPS_API_KEY = get_secret("GOOGLE_MAPS_API_KEY")

# [Custom settings]
CAPTCHA_PRIVATE_KEY = get_secret("CAPTCHA_PRIVATE_KEY")
CAPTCHA_PUBLIC_KEY = get_secret("CAPTCHA_PUBLIC_KEY")

# [Custom settings]
GOOGLE_ANALYTICS_CODE = get_secret("GOOGLE_ANALYTICS_CODE", required=False)


# VISION BACKEND SETTINGS
# TODO: move to separate settings file.
NEW_MODEL_THRESHOLD = 1.5
MIN_NBR_ANNOTATED_IMAGES = 5
NBR_IMAGES_PER_LOOP = 100
