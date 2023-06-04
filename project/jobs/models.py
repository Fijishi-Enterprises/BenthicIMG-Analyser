from django.db import models
from django.db.models import Q
from django.utils import timezone

from images.models import Source


class Job(models.Model):
    """
    Tracks any kind of asynchronous job/task.
    Don't have to track every single job/task like this; just ones we want to
    keep a closer eye on.
    """
    job_name = models.CharField(max_length=100)

    # Secondary identifier for this Job based on the arguments it was
    # called with. Jobs with the same name + args are considered to be
    # doing the same thing.
    arg_identifier = models.CharField(max_length=100, blank=True)

    # Source this Job applies to, if applicable.
    source = models.ForeignKey(Source, null=True, on_delete=models.CASCADE)

    class Status(models.TextChoices):
        PENDING = 'pending', "Pending"
        IN_PROGRESS = 'in_progress', "In Progress"
        SUCCESS = 'success', "Success"
        FAILURE = 'failure', "Failure"
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING)

    # Error message or comment about the job's result.
    result_message = models.CharField(max_length=500, blank=True)

    # If this is a retry of a failed Job, then we set this to be the previous
    # Job's attempt number + 1. This allows better tracking and debugging of
    # repeat failures.
    attempt_number = models.IntegerField(default=1)

    # Set this flag to prevent the Job from being purged from the DB
    # when it gets old enough.
    persist = models.BooleanField(default=False)

    # Date/time the Job was queued (pending).
    create_date = models.DateTimeField("Date created", auto_now_add=True)
    # Date/time the Job is scheduled to start, assuming server resources are
    # available then.
    scheduled_start_date = models.DateTimeField(
        "Scheduled start date", default=timezone.now)
    # Date/time the Job was modified. If the Job is done, this should tell us
    # how long the Job took. This is useful info for tuning
    # task delays / periodic runs.
    modify_date = models.DateTimeField("Date modified", auto_now=True)

    class Meta:
        constraints = [
            # There cannot be two identical Jobs among the
            # in-progress Jobs.
            models.UniqueConstraint(
                fields=['job_name', 'arg_identifier'],
                condition=Q(status='IP'),
                name='unique_running_jobs',
            ),
        ]

    def __str__(self):
        s = f"{self.job_name} / {self.arg_identifier}"
        if self.attempt_number > 1:
            s += f", attempt {self.attempt_number}"
        return s

    @staticmethod
    def args_to_identifier(args):
        return ','.join([str(arg) for arg in args])

    @staticmethod
    def identifier_to_args(identifier):
        """
        Note: this gets the args in string form, and doesn't work if the
        args themselves have , in them.
        """
        return identifier.split(',')
