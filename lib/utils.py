# General utility functions and classes can go here.

import json, os, random, string

from django.http import HttpResponse
from django.utils import functional


def JsonResponse(response):
    """
    Construct a JSON response to return from an Ajax views.
    Based on djcelery.views.JsonResponse.

    response - some data to convert to JSON and turn into an AJAX response.

    Example:
    return JsonResponse({'message': "Hello"})
    """
    return HttpResponse(json.dumps(response), content_type="application/json")


def rand_string(numOfChars):
    """
    Generates a string of lowercase letters and numbers.
    That makes 36^10 = 3 x 10^15 possibilities.

    If we generate filenames randomly, it's harder for people to guess filenames
    and type in their URLs directly to bypass permissions.
    """
    return ''.join(random.choice(string.ascii_lowercase + string.digits) for i in range(numOfChars))


def generate_random_filename(directory, originalFilename, numOfChars):
    """
    Generate a random filename for a file upload.  The filename will
    have numOfChars random characters.  Also prepends the directory
    argument to get a filepath which is only missing the MEDIA_ROOT
    part at the beginning.

    The return value can be used as an upload_to argument for a FileField
    ImageField, ThumbnailerImageField, etc.  An upload_to argument is
    automatically prepended with MEDIA_ROOT to get the upload filepath.
    """
    # TODO: Use the directory argument to check for filename collisions with existing files.
    # To unit test this, use a Mocker or similar on the filename randomizer
    # to make filename collisions far more likely.

    extension = os.path.splitext(originalFilename)[1]
    filenameBase = rand_string(numOfChars)
    return os.path.join(directory, filenameBase + extension)


def is_django_str(s):
    """
    Checks that the argument is either:
    (a) an instance of basestring, or
    (b) a Django lazy-translation string.

    :param s: Object to check the type of.
    :return: True if s is a Django string, False otherwise.
    """
    if isinstance(s, basestring):
        return True
    elif isinstance(s, functional.Promise):
        return True
    else:
        return False