import re
from django.contrib.staticfiles.templatetags.staticfiles \
    import static as to_static_path
from django.core.files.storage import get_storage_class
from django import template
from django.template import TemplateSyntaxError
from django.utils.html import escape
from django.utils import six
from easy_thumbnails.files import get_thumbnailer

from async_media.utils import set_async_media_request
from visualization.utils import get_patch_path, get_patch_url

register = template.Library()


RE_SIZE = re.compile(r'(\d+)x(\d+)$')
def parse_size(size):
    """
    Size variable can be either a tuple/list of two integers or a
    valid string.
    This is similar to how easy-thumbnails' template tag parses size.
    """
    if isinstance(size, six.string_types):
        m = RE_SIZE.match(size)
        if m:
            size = (int(m.group(1)), int(m.group(2)))
        else:
            raise TemplateSyntaxError(
                "{size} is not a valid size.".format(size=size))
    return size


def media_async(details, request):
    request_hash = set_async_media_request(details, request)

    # Display a 'loading' image to begin with.
    src = to_static_path(
        'img/placeholders/media-loading__{w}x{h}.png'.format(
            w=details['size'][0], h=details['size'][1]))

    return dict(src=src, async_request_hash=request_hash)


@register.simple_tag
def patch_async(point, request):
    """
    Image patch for an annotation point.
    """
    # Get the storage class, then get an instance of it.
    storage = get_storage_class()()
    # Check if patch exists for the point
    patch_relative_path = get_patch_path(point.pk)
    if storage.exists(patch_relative_path):
        return dict(src=escape(get_patch_url(point.pk)))

    # The patch doesn't exist. Prepare to generate it asynchronously.
    details_dict = dict(point_id=point.pk, size=(150, 150), media_type='patch')
    return media_async(details_dict, request)


@register.simple_tag
def thumbnail_async(source, size, request):
    """
    Alternate-size version of a media image.
    """
    size = parse_size(size)

    # generate=False turns off synchronous (blocking) generation.
    thumbnail = get_thumbnailer(source).get_thumbnail(
        dict(size=size), generate=False)

    if thumbnail:
        return dict(src=escape(thumbnail.url))

    # The thumbnail doesn't exist. Prepare to generate it asynchronously.
    details_dict = dict(name=source.name, size=size, media_type='thumbnail')
    return media_async(details_dict, request)
