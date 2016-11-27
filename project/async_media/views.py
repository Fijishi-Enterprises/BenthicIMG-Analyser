from django.contrib.staticfiles.templatetags.staticfiles \
    import static as to_static_path
from django.core.cache import cache
from django.http import JsonResponse
import easy_thumbnails.exceptions as easy_thumbnails_exceptions
from easy_thumbnails.files import get_thumbnailer

from .utils import (
    delete_thumbnail_request_status,
    get_thumbnail_request_status, get_thumbnail_url,
    set_thumbnail_request_status, set_thumbnail_url)


def thumbnails_ajax(request):
    hashes = request.POST.getlist('hashes[]')
    if not hashes:
        raise ValueError("No request hashes provided.")

    first_hash = hashes[0]
    status = dict(count=len(hashes), index=0)
    set_thumbnail_request_status(first_hash, status)

    for index, thumbnail_hash in enumerate(hashes):
        cache_key = 'thumbnail_async_request_{hash}'.format(
            hash=thumbnail_hash)
        if cache_key not in cache:
            raise ValueError("One or more request hashes were not found.")

        name, size, user_id = cache.get(cache_key)
        cache.delete(cache_key)

        not_found_image = to_static_path(
            'img/placeholders/'
            'thumbnail-image-not-found__{w}x{h}.png'.format(
                w=size[0], h=size[1]))

        if user_id and request.user.pk != user_id:
            # Security check: the user didn't match the original thumbnail
            # requester.
            url = not_found_image
        else:
            try:
                # Generate the thumbnail.
                thumbnail = get_thumbnailer(name).get_thumbnail(
                    dict(size=size), generate=True)
                url = thumbnail.url
            except easy_thumbnails_exceptions.InvalidImageFormatError:
                # We might get here if the original image file is not found.
                url = not_found_image

        set_thumbnail_url(first_hash, index, url)

    # Nothing to really return. The client should be getting the thumbnails
    # from the polling responses.
    return JsonResponse(dict())


def thumbnails_poll_ajax(request):
    first_hash = request.POST.get('first_hash')
    status = get_thumbnail_request_status(first_hash)

    if not status:
        # Perhaps the initial Ajax didn't complete yet. Try again later.
        return JsonResponse(dict(
            thumbnails=[], thumbnailsRemaining=True))

    thumbnails = []

    for index in range(status['index'], status['count']):
        url = get_thumbnail_url(first_hash, index)
        if not url:
            # The next thumbnail isn't available yet. Return the ones we have
            # so far.
            status['index'] = index
            set_thumbnail_request_status(first_hash, status)
            return JsonResponse(dict(
                thumbnails=thumbnails, thumbnailsRemaining=True))

        thumbnails.append(dict(index=index, url=url))

    # That's the last of the thumbnails.
    delete_thumbnail_request_status(first_hash)
    return JsonResponse(dict(
        thumbnails=thumbnails, thumbnailsRemaining=False))
