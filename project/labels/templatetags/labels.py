from django import template
from django.templatetags.static import static
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


@register.simple_tag
def verified_icon(label):
    if label.verified:
        icon_relative_path = 'img/verified__16x16.png'
    else:
        icon_relative_path = 'img/not-verified__16x16.png'

    # Call the 'static' template tag's code to get the full path.
    icon_full_path = static(icon_relative_path)

    return mark_safe(
        '<img class="verified-image" src="{src}" />'.format(
            src=icon_full_path))
