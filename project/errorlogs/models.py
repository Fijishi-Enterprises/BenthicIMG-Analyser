from __future__ import unicode_literals

from django.db.models import Model
from django.db.models.fields import CharField, DateTimeField, TextField, URLField
from django.utils.encoding import python_2_unicode_compatible


@python_2_unicode_compatible
class ErrorLog(Model):
    """
    Model for storing logs for individual errors.
    """
    kind = CharField("Type", null=True, blank=True, max_length=128)
    info = TextField(null=False)
    data = TextField(null=True, blank=True)
    path = URLField(null=True, blank=True)
    when = DateTimeField(null=False, auto_now_add=True)
    html = TextField(null=True, blank=True)

    class Meta:
        verbose_name = "Error log"
        verbose_name_plural = "Error logs"

    def __str__(self):
        return "%s: %s" % (self.kind, self.info)
