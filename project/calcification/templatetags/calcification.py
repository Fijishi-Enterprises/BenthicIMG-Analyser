from django import template
from django.templatetags.static import static
from django.utils.safestring import mark_safe

from ..utils import label_has_calcify_rates

register = template.Library()


@register.simple_tag
def calcify_rate_indicator(label, indicator_type):
    if indicator_type == 'icon':
        if label_has_calcify_rates(label):
            icon_relative_path = 'img/label-icon-calcify__16x16.png'
            alt_text = "Has calcification rate data"
            title_text = "Has calcification rate data"
        else:
            icon_relative_path = 'img/label-icon-neutral__16x16.png'
            alt_text = ""
            title_text = ""

        # Call the 'static' template tag's code to get the full path.
        icon_full_path = static(icon_relative_path)

        return mark_safe(
            '<img class="label-status-image" src="{src}" alt="{alt}"'
            ' title="{title}" />'.format(
                src=icon_full_path, alt=alt_text, title=title_text))

    elif indicator_type == 'text':
        if label_has_calcify_rates(label):
            return "Available"
        else:
            return "Not available"

    else:
        raise ValueError(f"Unsupported indicator_type: {indicator_type}")
