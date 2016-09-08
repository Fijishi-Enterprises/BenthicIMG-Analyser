from __future__ import unicode_literals

from django.db import models

from images.models import Source, Image

from annotations.models import Point, Label

# Create your models here.
class Classifier(models.Model):
    # Later, may tie robots to labelsets instead of sources
    source = models.ForeignKey(Source, on_delete=models.CASCADE)

    valid = models.BooleanField(default=False)
    
    version = models.IntegerField(unique=True)
    path_to_model = models.CharField(max_length=500)
    time_to_train = models.BigIntegerField()

    create_date = models.DateTimeField('Date created', auto_now_add=True, editable=False)
    
    def get_process_date_short_str(self):
        """
        Return the image's (pre)process date in YYYY-MM-DD format.

        Advantage over YYYY-(M)M-(D)D: alphabetized = sorted by date
        Advantage over YYYY(M)M(D)D: date is unambiguous
        """
        return "{0}-{1:02}-{2:02}".format(self.create_date.year, self.create_date.month, self.create_date.day)


    def __unicode__(self):
        """
        To-string method.
        """
        return "Version %s for %s" % (self.version, self.source.name)


class Score(models.Model):
    point = models.ForeignKey(Point, on_delete = models.CASCADE)
    label = models.ForeignKey(Label, on_delete = models.CASCADE)
    source = models.ForeignKey(Source, on_delete = models.CASCADE)
    #image = models.ForeignKey(Image, on_delete = models.CASCADE)
    score = models.IntegerField(default = 0)


    