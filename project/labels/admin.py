from django.contrib import admin
from .models import LabelGroup


@admin.register(LabelGroup)
class LabelGroupAdmin(admin.ModelAdmin):
    list_display = ('name', 'code')