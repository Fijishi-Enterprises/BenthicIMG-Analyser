from django import template

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
