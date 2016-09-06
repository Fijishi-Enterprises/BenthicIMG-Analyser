from django.contrib import admin
from .models import LabelGroup, Label


@admin.register(Label)
class LabelAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'group', 'create_date')


@admin.register(LabelGroup)
class LabelGroupAdmin(admin.ModelAdmin):
    list_display = ('name', 'code')
