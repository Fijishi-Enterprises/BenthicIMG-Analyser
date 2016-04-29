import sys
import traceback

from django.http import Http404
from django.views.debug import ExceptionReporter

from .models import ErrorLog


def handle_request_exception(sender, request=None, *args, **kwargs):
    """
    Handles the request exception signal.
    Saves a log of the error to the database.
    """
    # Get the most recent exception's info.
    kind, info, data = sys.exc_info()

    if not issubclass(kind, Http404):

        error_log = ErrorLog(
            kind=kind.__name__,
            html=ExceptionReporter(request, kind, info, data).get_traceback_html(),
            path=request.build_absolute_uri(),
            info=info,
            data='\n'.join(traceback.format_exception(kind, info, data)),
        )
        error_log.save()