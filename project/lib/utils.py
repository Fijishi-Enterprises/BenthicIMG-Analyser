# General utility functions and classes can go here.

import math
import random
import string

from django.utils import functional


def filesize_display(num_bytes):
    """
    Return a human-readable filesize string in B, KB, MB, or GB.
    """
    KILO = 1024
    MEGA = 1024 * 1024
    GIGA = 1024 * 1024 * 1024

    if num_bytes < KILO:
        return "{n} B".format(n=num_bytes)
    if num_bytes < MEGA:
        return "{n:.2f} KB".format(n=math.floor(num_bytes / KILO))
    if num_bytes < GIGA:
        return "{n:.2f} MB".format(n=math.floor(num_bytes / MEGA))
    return "{n:.2f} GB".format(n=math.floor(num_bytes / GIGA))


def rand_string(num_of_chars):
    """
    Generates a string of lowercase letters and numbers.

    If we generate filenames randomly, it's harder for people to guess
    filenames and type in their URLs directly to bypass permissions.
    With 10 characters for example, we have 36^10 = 3 x 10^15 possibilities.
    """
    return ''.join(
        random.choice(string.ascii_lowercase + string.digits)
        for _ in range(num_of_chars))


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