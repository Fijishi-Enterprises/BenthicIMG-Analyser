from django.db import models


class LabelGroupManager(models.Manager):
    def get_by_natural_key(self, code):
        """
        Allow fixtures to refer to Label Groups by short code instead of by id.
        """
        return self.get(code=code)

class LabelGroup(models.Model):
    objects = LabelGroupManager()

    name = models.CharField(max_length=45, blank=True)
    code = models.CharField(max_length=10, blank=True)

    def __unicode__(self):
        """
        To-string method.
        """
        return self.name
