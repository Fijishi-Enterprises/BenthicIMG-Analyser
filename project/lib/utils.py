# General utility functions and classes can go here.

import math
import random
import string
import boto
import json
import pickle

from django.conf import settings
from django.core.paginator import Paginator, EmptyPage, InvalidPage
from django.utils import functional


def direct_s3_read(key, encoding):

    encoding_map = {
        'json': json.loads,
        'pickle': pickle.loads
    }

    conn = boto.connect_s3(
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY
    )
    bucket = conn.get_bucket(settings.AWS_STORAGE_BUCKET_NAME)
    k = boto.s3.key.Key(bucket)
    k.key = key
    
    return encoding_map[encoding](k.get_contents_as_string())

def direct_s3_write(key, encoding, data):

    encoding_map = {
        'json': json.dumps,
        'pickle': pickle.dumps
    }

    conn = boto.connect_s3(
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY
    )
    bucket = conn.get_bucket(settings.AWS_STORAGE_BUCKET_NAME)
    k = boto.s3.key.Key(bucket)
    k.key = key
    k.set_contents_from_string(encoding_map[encoding](data))


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


def paginate(results, items_per_page, request_args):
    """
    Helper for paginated views.
    Assumes the page number is in the GET parameter 'page'.
    """
    paginator = Paginator(results, items_per_page)
    request_args = request_args or dict()

    # Make sure page request is an int. If not, deliver first page.
    try:
        page = int(request_args.get('page', '1'))
    except ValueError:
        page = 1

    # If page request is out of range, deliver last page of results.
    try:
        page_results = paginator.page(page)
    except (EmptyPage, InvalidPage):
        page_results = paginator.page(paginator.num_pages)

    return page_results


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