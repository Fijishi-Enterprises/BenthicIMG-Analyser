from images.models import Source, Image, Metadata
from django.contrib import admin
from guardian.admin import GuardedModelAdmin

@admin.register(Source)
class SourceAdmin(GuardedModelAdmin):
    list_display = ('name', 'visibility', 'create_date')

@admin.register(Image)
class ImageAdmin(admin.ModelAdmin):
    list_display = ('original_file', 'source', 'metadata')

@admin.register(Metadata)
class MetadataAdmin(admin.ModelAdmin):
    list_display = ('name', 'aux1', 'aux2', 'aux3', 'aux4', 'aux5')
