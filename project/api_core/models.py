from __future__ import unicode_literals
from collections import Counter

from django.contrib.auth.models import User
from django.db import models
from django.contrib.postgres.fields import JSONField


class ApiJob(models.Model):
    """
    Asynchronous jobs that were requested via the API.
    """
    # String specifying the type of job, e.g. deploy.
    type = models.CharField(max_length=30)

    # User who requested this job. Can be used for permissions on viewing
    # job status and results.
    user = models.ForeignKey(User, on_delete=models.CASCADE)

    # This can be used to report how long the job took or is taking.
    create_date = models.DateTimeField("Date created", auto_now_add=True)

    PENDING = "Pending"
    IN_PROGRESS = "In Progress"
    DONE = "Done"

    @property
    def status(self):
        """Just return the overall job status from full_status()."""
        return self.full_status()['overall_status']

    def full_status(self):
        """Report job status based on the statuses of the job units."""
        job_units = self.apijobunit_set
        job_unit_statuses = job_units.values_list('status', flat=True)
        counts = Counter(job_unit_statuses)
        total_unit_count = len(job_unit_statuses)

        if counts[ApiJobUnit.PENDING] == len(job_unit_statuses):
            # All units are still pending, so the job as a whole is pending
            overall_status = self.PENDING
        elif counts[ApiJobUnit.PENDING] + counts[ApiJobUnit.IN_PROGRESS] > 0:
            # Some units haven't finished yet, so the job isn't done yet
            overall_status = self.IN_PROGRESS
        else:
            # Job is done
            overall_status = self.DONE

        return dict(
            overall_status=overall_status,
            pending_units=counts[ApiJobUnit.PENDING],
            in_progress_units=counts[ApiJobUnit.IN_PROGRESS],
            failure_units=counts[ApiJobUnit.FAILURE],
            success_units=counts[ApiJobUnit.SUCCESS],
            total_units=total_unit_count,
        )


class ApiJobUnit(models.Model):
    """
    A smaller unit of work within an ApiJob.
    """
    # The larger job that this unit is a part of.
    job = models.ForeignKey(ApiJob, on_delete=models.CASCADE)

    # String specifying the type of job unit, in case a single job has more
    # than one type of unit.
    type = models.CharField(max_length=30)

    PENDING = 'PN'
    IN_PROGRESS = 'IP'
    SUCCESS = 'SC'
    FAILURE = 'FL'

    STATUS_CHOICES = [
        (PENDING, "Pending"),
        (IN_PROGRESS, "In Progress"),
        (SUCCESS, "Success"),
        (FAILURE, "Failure"),
    ]
    status = models.CharField(
        max_length=2, choices=STATUS_CHOICES, default=PENDING)

    # JSON containing data on the requested work. The exact format depends
    # on the type of job unit.
    request_json = JSONField()

    # JSON results of the job unit when it's done. The exact format depends
    # on the type of job.
    result_json = JSONField(null=True)

    # This can be used to report how long the job unit took or is taking
    # (including time waiting on the queue).
    create_date = models.DateTimeField("Date created", auto_now_add=True)

    # We can clean up old jobs if they haven't been modified in a while.
    modify_date = models.DateTimeField("Date last modified", auto_now=True)
