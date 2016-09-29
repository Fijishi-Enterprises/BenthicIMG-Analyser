from django import template
from django.utils.safestring import mark_safe

register = template.Library()


@register.simple_tag
def popularity_bar(label, short=False):
    if label.popularity >= 30:
        color = 'green'
    else:
        color = 'red'

    if short:
        meter_class = 'meter short'
    else:
        meter_class = 'meter'

    # float -> int to truncate decimal, then int -> str
    bar_width = str(int(label.popularity)) + '%'
    return mark_safe(
        '<div class="{meter_class}">'
        '  <span class="{color}" style="width: {bar_width};"></span>'
        '</div>'.format(
            meter_class=meter_class, color=color, bar_width=bar_width)
    )
