import re
from django.contrib.staticfiles.templatetags.staticfiles \
    import static as to_static_path
from django import template
from django.template import TemplateSyntaxError
from django.utils.html import escape
from django.utils import six
from easy_thumbnails.files import get_thumbnailer

from async_media.utils import set_async_thumbnail_request

register = template.Library()


RE_SIZE = re.compile(r'(\d+)x(\d+)$')
@register.simple_tag
def thumbnail_async(source, size, request):
    """
    Similar to easy-thumbnails' thumbnail tag, but with support for
    asynchronous thumbnail generation.
    """

    # Size variable can be either a tuple/list of two integers or a
    # valid string.
    if isinstance(size, six.string_types):
        m = RE_SIZE.match(size)
        if m:
            size = (int(m.group(1)), int(m.group(2)))
        else:
            raise TemplateSyntaxError(
                "{size} is not a valid size.".format(size=size))

    # generate=False turns off synchronous (blocking) generation.
    thumbnail = get_thumbnailer(source).get_thumbnail(
        dict(size=size), generate=False)

    if thumbnail:
        # The thumbnail exists.
        return dict(src=escape(thumbnail.url))

    # The thumbnail doesn't exist. Prepare to generate it asynchronously.
    request_hash = set_async_thumbnail_request(source.name, size, request)

    # Display a 'loading' image to begin with.
    src = to_static_path(
        'img/placeholders/thumbnail-loading__{w}x{h}.png'.format(
            w=size[0], h=size[1]))

    return dict(src=src, async_request_hash=request_hash)
