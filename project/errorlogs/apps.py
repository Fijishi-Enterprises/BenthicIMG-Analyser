# This app is roughly based on:
# https://github.com/mhsiddiqui/django-error-report
#
# And originally this SO answer, which used a signal instead of middleware,
# but saving the logs to the DB ended up not meshing well with the timing of
# DB transactions:
# http://stackoverflow.com/a/7579467

from django.apps import AppConfig


class ErrorlogsConfig(AppConfig):
    name = 'errorlogs'
    verbose_name = "Error Logs"
