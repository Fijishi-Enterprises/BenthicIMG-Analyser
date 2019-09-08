from __future__ import unicode_literals

from django.contrib import admin
from django.contrib.flatpages.admin import (
    FlatPageAdmin as DefaultFlatPageAdmin)
from django.contrib.flatpages.forms import FlatpageForm as DefaultFlatPageForm
from django.contrib.flatpages.models import FlatPage
from markdownx.widgets import AdminMarkdownxWidget


# Since FlatPage is already admin-registered by Django, we have to
# unregister it before re-registering it with our own class.
admin.site.unregister(FlatPage)


class FlatPageForm(DefaultFlatPageForm):
    class Meta:
        # Use the markdownx widget for the content field.
        widgets = dict(
            content=AdminMarkdownxWidget(),
        )


@admin.register(FlatPage)
class FlatPageAdmin(DefaultFlatPageAdmin):
    form = FlatPageForm
