# Here's an example of what settings_2.py should look like.
#
# settings_2.py should *not* be tracked by the Git repository.
# settings_2.py is for settings that should be different between
# development copies and the production server.  (The main settings
# file, settings.py, *is* tracked by Git and will import from
# settings_2.py.)
#
# Remember to create your own settings_2.py, and keep an eye out for
# updates to this example file; make sure your settings_2.py has all
# the settings that this example file has.
#
# Please update this example file if you encounter any additional
# settings that should go in settings_2.py.

DEBUG = True

ADMINS = (
    # ('Your Name', 'your_email@example.com'),
)

MANAGERS = ADMINS

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql', # Add 'postgresql_psycopg2', 'postgresql', 'mysql', 'sqlite3' or 'oracle'.
        'NAME': 'coralnet',                      # Or path to database file if using sqlite3.
        'USER': 'django',                      # Not used with sqlite3.
        'PASSWORD': 'djangor0cks',                  # Not used with sqlite3.
        'HOST': '',                      # Set to empty string for localhost. Not used with sqlite3.
        'PORT': '',                      # Set to empty string for default. Not used with sqlite3.
    }
}

FILE_UPLOAD_MAX_MEMORY_SIZE = 52428800  # 50 MB

# Absolute path to the directory static files should be collected to.
# Don't put anything in this directory yourself; store your static files
# in apps' "static/" subdirectories and in STATICFILES_DIRS.
# Example: "/home/media/media.lawrence.com/static/"
STATIC_ROOT = ''

# Make this unique, and don't share it with anybody.
SECRET_KEY = 'tg5t&4x9f8edmnhe)d55tkk$e-djc4m_q%=^xo%n-jipn&v&8j'