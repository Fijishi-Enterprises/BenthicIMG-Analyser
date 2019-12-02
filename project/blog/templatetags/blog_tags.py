from __future__ import unicode_literals

from django import template

from ..models import Entry

register = template.Library()


@register.filter(name='author_display')
def author_display(author, *args):
    """Given the User `author`, return an appropriate string for a
    blog entry's author display. Full name if available, else username.
    This replaces andablog's similar authordisplay template tag, which
    has different behavior (mainly, doesn't include last name)."""

    if author.first_name and author.last_name:
        return author.get_full_name()
    else:
        return author.username


@register.simple_tag
def blog_latest_entries(count):
    """
    Return the <count> latest published blog entries, ordered latest-first.
    """
    return Entry.objects.get_published()[:count]
