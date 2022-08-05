import sys
import traceback

from django.http import Http404
from django.views.debug import ExceptionReporter

from .models import ErrorLog


class SaveLogsToDatabaseMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.error_log = None

    def __call__(self, request):
        response = self.get_response(request)

        if self.error_log:
            # Now that we're outside of the view's transaction, save any
            # error that was logged earlier.
            self.error_log.save()
            self.error_log = None
        return response

    def process_exception(self, request, exception):
        """
        Handles errors raised during views.
        """
        # Get the most recent exception's info.
        kind, info, data = sys.exc_info()

        if not issubclass(kind, Http404):

            def replace_null(s):
                """
                It's apparently possible to get null chars in at least one of
                the error log char/text fields, which makes PostgreSQL get
                "A string literal cannot contain NUL (0x00) characters" upon
                saving the error log. So, replace null chars with
                a Replacement Character (question mark diamond).
                """
                return s.replace('\x00', '\uFFFD')

            # Create an ErrorLog to save to the database, but don't actually
            # save it yet, since we're still inside of the view's transaction.
            # We'll save it later in __call__() when the view returns.
            error_html = ExceptionReporter(
                request, kind, info, data).get_traceback_html()
            error_data = '\n'.join(traceback.format_exception(kind, info, data))
            self.error_log = ErrorLog(
                kind=kind.__name__,
                html=replace_null(error_html),
                path=replace_null(request.build_absolute_uri()),
                info=info,
                data=replace_null(error_data),
            )
