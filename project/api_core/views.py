from __future__ import unicode_literals

from .parsers import JSONAPIParser
from .renderers import JSONAPIRenderer
from .utils import BurstRateThrottle, SustainedRateThrottle
from rest_framework.authtoken.views import (
    ObtainAuthToken as DefaultObtainAuthToken)


class ObtainAuthToken(DefaultObtainAuthToken):
    """
    Subclass of rest-framework's token view, in order to:
    1. Add throttling, since the view doesn't have throttling by default:
    https://www.django-rest-framework.org/api-guide/authentication/#by-exposing-an-api-endpoint
    2. Use our custom parser, since the view defaults to DRF's JSON
    parser instead of using our parser settings.
    3. Use our custom renderer, since the view defaults to DRF's JSON
    renderer instead of using our renderer settings.
    """
    throttle_classes = [BurstRateThrottle, SustainedRateThrottle]
    parser_classes = [JSONAPIParser]
    renderer_classes = [JSONAPIRenderer]
