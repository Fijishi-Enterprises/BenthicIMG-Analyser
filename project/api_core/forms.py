# Django's forms system seems to have limited use for our API, since:
# - Django doesn't seem to have JSON field validators.
# - There's no clean way to specify the error 'source' as a JSON pointer.
#   The cleanest way would have been to raise ValidationErrors like
#   "This field is required. | /images/2", then parse the message and
#   JSON pointer out of that string by splitting at the |.
# So we more or less roll our own validation. We still put it in 'forms.py'
# since that filename is generally associated with validating user input.

import collections.abc

from .exceptions import ApiRequestDataError


def validate_array(element, json_path, check_non_empty=False, max_length=None):
    # We use MutableSequence instead of Sequence to avoid matching strings.
    if not isinstance(element, collections.abc.MutableSequence):
        raise ApiRequestDataError(
            "Ensure this element is an array.", json_path)
    if check_non_empty:
        if len(element) == 0:
            raise ApiRequestDataError(
                "Ensure this array is non-empty.", json_path)
    if max_length:
        if len(element) > max_length:
            message = "This array exceeds the max length of {max}.".format(
                max=max_length)
            raise ApiRequestDataError(message, json_path)


def validate_hash(element, json_path, expected_keys=None):
    if not isinstance(element, collections.abc.Mapping):
        raise ApiRequestDataError("Ensure this element is a hash.", json_path)
    if expected_keys:
        for key in expected_keys:
            if key not in element:
                raise ApiRequestDataError(
                    "Ensure this hash has a '{key}' key.".format(key=key),
                    json_path)


def validate_integer(element, json_path, min_value=None, max_value=None):
    if not isinstance(element, int):
        raise ApiRequestDataError(
            "Ensure this element is an integer.", json_path)

    if min_value is not None:
        if element < min_value:
            raise ApiRequestDataError(
                "This element's value is below the minimum"
                " of {min}.".format(min=min_value),
                json_path)
    if max_value is not None:
        if element > max_value:
            raise ApiRequestDataError(
                "This element's value is above the maximum"
                " of {max}.".format(max=max_value),
                json_path)


def validate_string(element, json_path, equal_to=None):
    if not isinstance(element, str):
        raise ApiRequestDataError(
            "Ensure this element is a string.", json_path)
    if equal_to is not None:
        if element != equal_to:
            raise ApiRequestDataError(
                "This element should be equal to '{s}'.".format(s=equal_to),
                json_path)
