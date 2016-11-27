from django.contrib.staticfiles.templatetags.staticfiles \
    import static as to_static_path
from django.core.cache import cache
from django.http import JsonResponse
import easy_thumbnails.exceptions as easy_thumbnails_exceptions
from easy_thumbnails.files import get_thumbnailer

from visualization.utils import generate_patch_if_doesnt_exist, get_patch_url
from .utils import (
    delete_media_request_status,
    get_media_request_status, get_media_url,
    set_media_request_status, set_media_url)


def media_ajax(request):
    hashes = request.POST.getlist('hashes[]')
    if not hashes:
        raise ValueError("No request hashes provided.")

    first_hash = hashes[0]
    status = dict(count=len(hashes), index=0)
    set_media_request_status(first_hash, status)

    for index, media_hash in enumerate(hashes):
        cache_key = 'media_async_request_{hash}'.format(
            hash=media_hash)
        if cache_key not in cache:
            raise ValueError("One or more request hashes were not found.")

        details = cache.get(cache_key)
        cache.delete(cache_key)

        size = details['size']
        not_found_image = to_static_path(
            'img/placeholders/'
            'media-image-not-found__{w}x{h}.png'.format(
                w=size[0], h=size[1]))

        if details['user_id'] and request.user.pk != details['user_id']:
            # Security check: the user didn't match the original media
            # requester.
            url = not_found_image
        elif details['media_type'] == 'thumbnail':
            try:
                # Generate the media.
                thumbnail = get_thumbnailer(details['name']).get_thumbnail(
                    dict(size=size), generate=True)
                url = thumbnail.url
            except easy_thumbnails_exceptions.InvalidImageFormatError:
                # We might get here if the original image file is not found.
                url = not_found_image
        elif details['media_type'] == 'patch':
            # Generate the media.
            generate_patch_if_doesnt_exist(details['point_id'])
            url = get_patch_url(details['point_id'])
        else:
            # Unknown media type for some reason.
            url = not_found_image

        set_media_url(first_hash, index, url)

    # Nothing to really return. The client should be getting the media
    # from the polling responses.
    return JsonResponse(dict())


def media_poll_ajax(request):
    first_hash = request.POST.get('first_hash')
    status = get_media_request_status(first_hash)

    if not status:
        # Perhaps the initial Ajax didn't complete yet. Try again later.
        return JsonResponse(dict(
            media=[], mediaRemaining=True))

    media = []

    for index in range(status['index'], status['count']):
        url = get_media_url(first_hash, index)
        if not url:
            # The next media file isn't available yet. Return the ones we have
            # so far.
            status['index'] = index
            set_media_request_status(first_hash, status)
            return JsonResponse(dict(
                media=media, mediaRemaining=True))

        media.append(dict(index=index, url=url))

    # That's the last of the media.
    delete_media_request_status(first_hash)
    return JsonResponse(dict(
        media=media, mediaRemaining=False))
