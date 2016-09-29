from django import template
from django.utils.safestring import mark_safe

register = template.Library()


@register.simple_tag
def popularity_bar(label):
    if label.popularity >= 30:
        color = 'green'
    else:
        color = 'red'
    # float -> int to truncate decimal, then int -> str
    bar_width = str(int(label.popularity)) + '%'
    return mark_safe(
        '<div class="meter">'
        '  <span class="{color}" style="width: {bar_width};"></span>'
        '</div>'.format(color=color, bar_width=bar_width)
    )
