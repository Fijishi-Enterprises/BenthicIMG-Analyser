from django.contrib import admin
from reversion.admin import VersionAdmin
from .models import Label, LabelSet, Annotation

@admin.register(Label)
class LabelAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'group', 'create_date')

@admin.register(LabelSet)
class LabelSetAdmin(admin.ModelAdmin):
    pass

# Inherit from reversion.VersionAdmin to enable versioning for a particular model.
@admin.register(Annotation)
class AnnotationAdmin(VersionAdmin):
    list_display = ('source', 'image', 'point')
