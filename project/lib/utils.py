# General utility functions and classes can go here.

import random, string

from django.utils import functional


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