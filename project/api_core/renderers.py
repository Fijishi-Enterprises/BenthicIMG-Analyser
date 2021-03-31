from rest_framework.renderers import JSONRenderer


class JSONAPIRenderer(JSONRenderer):
    # Send responses of Content-Type 'application/vnd.api+json' instead of
    # 'application/json'.
    # https://jsonapi.org/format/#content-negotiation-clients
    media_type = 'application/vnd.api+json'
