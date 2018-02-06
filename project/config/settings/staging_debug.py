# Settings for running the staging server with the runserver command,
# for easier debugging.
# To view the staging server when it's using runserver, use an SSH tunnel.

from .staging import *

DEBUG = True
ALLOWED_HOSTS = ['*']

