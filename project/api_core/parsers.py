from rest_framework.parsers import JSONParser


class JSONAPIParser(JSONParser):
    # Accept requests of Content-Type 'application/vnd.api+json' instead of
    # 'application/json'.
    # https://jsonapi.org/format/#content-negotiation-clients
    media_type = 'application/vnd.api+json'
