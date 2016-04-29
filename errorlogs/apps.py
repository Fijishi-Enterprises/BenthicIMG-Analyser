# This app is based on this SO answer:
# http://stackoverflow.com/a/7579467

from __future__ import unicode_literals

from django.apps import AppConfig
from django.core.signals import got_request_exception


class ErrorlogsConfig(AppConfig):
    name = 'errorlogs'
    verbose_name = "Error Logs"

    def ready(self):
        # Putting this import at the top of the module gets an
        # AppRegistryNotReady exception, so we put it here instead.
        from . import signals

        got_request_exception.connect(signals.handle_request_exception)
