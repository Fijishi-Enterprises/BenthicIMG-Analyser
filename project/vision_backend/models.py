from django.conf import settings
from django.core.files.storage import get_storage_class
from django.db import models
from spacer.data_classes import ValResults
from spacer.messages import DataLocation

from jobs.models import Job
from labels.models import Label, LocalLabel


class Classifier(models.Model):
    """
    Computer vision classifier.
    """

    # pointer to the source
    source = models.ForeignKey('images.Source', on_delete=models.CASCADE)

    TRAIN_PENDING = 'PN'
    LACKING_UNIQUE_LABELS = 'UQ'
    TRAIN_ERROR = 'ER'
    REJECTED_ACCURACY = 'RJ'
    ACCEPTED = 'AC'
    STATUS_CHOICES = [
        (TRAIN_PENDING, "Training pending"),
        (LACKING_UNIQUE_LABELS,
         "Declined because the training labelset only had one unique label"),
        (TRAIN_ERROR, "Training got an error"),
        (REJECTED_ACCURACY, "Rejected because accuracy didn't improve enough"),
        (ACCEPTED, "Accepted as new classifier"),
    ]
    # Training status of the classifier.
    status = models.CharField(
        max_length=2, choices=STATUS_CHOICES, default=TRAIN_PENDING)

    # Training runtime in seconds.
    runtime_train = models.BigIntegerField(default=0)

    # Accuracy as evaluated on the validation set
    accuracy = models.FloatField(null=True)

    # Epoch reference set accuracy (for bookkeeping mostly)
    epoch_ref_accuracy = models.CharField(max_length=512, null=True)

    # Number of image (val + train) that were used to train this classifier
    nbr_train_images = models.IntegerField(null=True)

    # Create date
    create_date = models.DateTimeField('Date created', auto_now_add=True,
                                       editable=False)
    
    @property
    def valres(self) -> ValResults:
        storage = get_storage_class()()
        valres_loc: DataLocation = storage.spacer_data_loc(
            settings.ROBOT_MODEL_VALRESULT_PATTERN.format(pk=self.pk))

        return ValResults.load(valres_loc)

    def get_process_date_short_str(self):
        """
        Return the image's (pre)process date in YYYY-MM-DD format.

        Advantage over YYYY-(M)M-(D)D: alphabetized = sorted by date
        Advantage over YYYY(M)M(D)D: date is unambiguous
        """
        return "{0}-{1:02}-{2:02}".format(self.create_date.year,
                                          self.create_date.month,
                                          self.create_date.day)

    def __str__(self):
        """
        To-string method.
        """
        return (
            f"Classifier {self.pk}"
            f" [Source: {self.source} [{self.source.pk}]]")


class Features(models.Model):
    """
    This class manages the bookkeeping of features for each image.
    """
    image = models.OneToOneField('images.Image', on_delete=models.CASCADE)

    # Indicates whether the features are extracted. Set when jobs are collected
    extracted = models.BooleanField(default=False)

    # Indicates whether features are classified by any version of the robot.
    classified = models.BooleanField(default=False)

    # total runtime for job
    runtime_total = models.IntegerField(null=True)

    # runtime for the call to caffe
    runtime_core = models.IntegerField(null=True)

    # whether the model needed to be downloaded from S3
    model_was_cashed = models.NullBooleanField(null=True)

    # When were the features extracted
    extracted_date = models.DateTimeField(null=True)


class Score(models.Model):
    """
    Tracks scores for each point in each image. For each point,
    scores for only the top NBR_SCORES_PER_ANNOTATION labels are saved.
    """
    # Use BigAutoField instead of AutoField to handle IDs over (2**31)-1.
    id = models.BigAutoField(primary_key=True)

    label = models.ForeignKey(Label, on_delete=models.CASCADE)
    point = models.ForeignKey('images.Point', on_delete=models.CASCADE)
    source = models.ForeignKey('images.Source', on_delete=models.CASCADE)
    image = models.ForeignKey('images.Image', on_delete=models.CASCADE)

    # Integer between 0 and 99, representing the percent probability
    # that this point is this label according to the backend. Although
    # scores are only saved for the top NBR_SCORES_PER_ANNOTATION labels,
    # this is the probability among all labels in the labelset.
    score = models.IntegerField(default=0)

    @property
    def label_code(self):
        local_label = LocalLabel.objects.get(
            global_label=self.label, labelset=self.source.labelset)
        return local_label.code

    def __str__(self):
        return "%s - %s - %s - %s" % (
            self.image, self.point.point_number, self.label_code, self.score)


class BatchJob(models.Model):
    """
    Simple table that tracks the AWS Batch job tokens and status.
    """
    STATUS_CHOICES = [
        ('SUBMITTED', 'SUBMITTED'),
        ('PENDING', 'PENDING'),
        ('RUNNABLE', 'RUNNABLE'),
        ('STARTING', 'STARTING'),
        ('RUNNING', 'RUNNING'),
        ('SUCCEEDED', 'SUCCEEDED'),
        ('FAILED', 'FAILED'),
    ]

    def __str__(self):
        return (
            f"BatchJob {self.pk}, for Job {self.internal_job}")

    # The status taxonomy is from AWS Batch.
    status = models.CharField(
        max_length=12, choices=STATUS_CHOICES, default='SUBMITTED')

    # Unique job identifier returned by Batch.
    batch_token = models.CharField(max_length=128, null=True)

    # Job instance that this BatchJob is associated with.
    # When the Job is cleaned up, this BatchJob also gets cleaned up via
    # cascade-delete.
    internal_job = models.OneToOneField(Job, on_delete=models.CASCADE)

    # This can be used to see long the BatchJob is taking.
    create_date = models.DateTimeField("Date created", auto_now_add=True)

    @property
    def job_key(self):
        return settings.BATCH_JOB_PATTERN.format(pk=self.id)

    @property
    def res_key(self):
        return settings.BATCH_RES_PATTERN.format(pk=self.id)

    def make_batch_job_name(self):
        """
        This is just a name that can be useful for identifying Batch jobs
        when browsing the AWS Batch console.
        However, the Batch token is what's actually used to retrieve
        previously-submitted Batch jobs.
        """
        # Using the SPACER_JOB_HASH allows us to differentiate between
        # submissions from production, staging, and different dev setups.
        return (
            f'{settings.SPACER_JOB_HASH}'
            f'-{self.internal_job.job_name}'
            f'-{self.internal_job.pk}')
