from django.contrib import admin
from django.contrib.admin.utils import unquote
from django.utils.safestring import mark_safe

from .models import ErrorLog


@admin.register(ErrorLog)
class ErrorLogAdmin(admin.ModelAdmin):
    list_display    = ('path', 'kind', 'info', 'when')
    list_display_links = ('path',)
    ordering        = ('-id',)
    search_fields   = ('path', 'kind', 'info', 'data')
    readonly_fields = ('path', 'kind', 'info', 'data', 'when', 'html',)
    fieldsets       = (
        (None, {
            'fields': ('kind', 'data', 'info')
        }),
    )

    def change_view(self, request, object_id, form_url='', extra_context=None):
        """
        The detail view of the error record.
        """
        obj = self.get_object(request, unquote(object_id))

        if not extra_context:
            extra_context = dict()
        extra_context.update({
            'instance': obj,
            'error_body': mark_safe(obj.html),
        })

        return super().change_view(
            request, object_id, form_url, extra_context)