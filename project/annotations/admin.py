from django.contrib import admin
from reversion.admin import VersionAdmin
from .models import Annotation


# Inherit from reversion.VersionAdmin
# to enable versioning for a model.
@admin.register(Annotation)
class AnnotationAdmin(VersionAdmin):
    list_display = ('source', 'image', 'point')
