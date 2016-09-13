from __future__ import unicode_literals

from django.db import models

from datetime import datetime

class Classifier(models.Model):
    """
    Computer vision classifier.
    """

    source = models.ForeignKey('images.Source', on_delete=models.CASCADE)

    valid = models.BooleanField(default=False)

    runtime_train = models.BigIntegerField(default = 0)

    nbr_train_images = models.IntegerField(null = True)

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


class Features(models.Model):
    """
    This class manages the bookkeeping of features for each image.
    """

    extracted = models.BooleanField(default = False)
    classified = models.BooleanField(default = False)

    runtime_total = models.IntegerField(null = True)
    runtime_core = models.IntegerField(null = True)

    extracted_date = models.DateTimeField(null = True)



class Score(models.Model):
    """
    Tracks scores for each point in each image.
    """
    label = models.ForeignKey('annotations.Label', on_delete = models.CASCADE)
    point = models.ForeignKey('images.Point', on_delete = models.CASCADE)
    source = models.ForeignKey('images.Source', on_delete = models.CASCADE)
    image = models.ForeignKey('images.Image', on_delete = models.CASCADE)
    score = models.IntegerField(default = 0)


    