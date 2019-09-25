from __future__ import unicode_literals

from django.contrib import admin
from django.contrib.flatpages.admin import (
    FlatPageAdmin as DefaultFlatPageAdmin)
from django.contrib.flatpages.forms import FlatpageForm as DefaultFlatPageForm
from django.contrib.flatpages.models import FlatPage
from markdownx.widgets import AdminMarkdownxWidget
from reversion.admin import VersionAdmin


# Since FlatPage is already admin-registered by Django, we have to
# unregister it before re-registering it with our own class.
admin.site.unregister(FlatPage)


class FlatPageForm(DefaultFlatPageForm):
    class Media:
        css = {
            'all': ("css/markdownx_editor.css",)
        }
    class Meta:
        # Use the markdownx widget for the content field.
        widgets = dict(
            content=AdminMarkdownxWidget(),
        )


# With VersionAdmin, saving flatpages via site views (admin or otherwise)
# should trigger saving of django-reversion Versions.
@admin.register(FlatPage)
class FlatPageAdmin(DefaultFlatPageAdmin, VersionAdmin):
    form = FlatPageForm
