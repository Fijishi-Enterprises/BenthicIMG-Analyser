# General utility functions and classes can go here.

import datetime
import random
import string

from django.core.paginator import Paginator, EmptyPage, InvalidPage


def filesize_display(num_bytes):
    """
    Return a human-readable filesize string in B, KB, MB, or GB.

    TODO: We may want an option here for number of decimal places or
    sig figs, since it's used for filesize limit displays. As a limit
    description, '30 MB' makes more sense than '30.00 MB'.
    """
    KILO = 1024
    MEGA = 1024 * 1024
    GIGA = 1024 * 1024 * 1024

    if num_bytes < KILO:
        return "{n} B".format(n=num_bytes)
    if num_bytes < MEGA:
        return "{n:.2f} KB".format(n=num_bytes / KILO)
    if num_bytes < GIGA:
        return "{n:.2f} MB".format(n=num_bytes / MEGA)
    return "{n:.2f} GB".format(n=num_bytes / GIGA)


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


def save_session_data(session, key, data):
    """
    Save data to session, then return a timestamp. This timestamp should be
    sent to the server by any subsequent request which wants to get this
    session data. Generally, the key verifies which page the session data is
    for, and the timestamp verifies that it's for a particular visit/request
    on that page. This ensures that nothing chaotic happens if a single user
    opens multiple browser tabs on session-using pages.

    An example use of sessions in CoralNet is to do a GET non-Ajax file-serve
    after a POST Ajax processing step. Lengthy processing is better as Ajax
    for browser responsiveness, and file serving is more natural as non-Ajax.
    """
    timestamp = str(datetime.datetime.now().timestamp())
    session[key] = dict(data=data, timestamp=timestamp)
    return timestamp
