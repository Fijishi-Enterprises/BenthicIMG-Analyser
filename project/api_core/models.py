from collections import Counter

from django.contrib.auth.models import User
from django.db import models

from jobs.models import Job


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
        job_unit_statuses = job_units.values_list(
            'internal_job__status', flat=True)
        counts = Counter(job_unit_statuses)
        total_unit_count = len(job_unit_statuses)

        if counts[Job.PENDING] == len(job_unit_statuses):
            # All units are still pending, so the job as a whole is pending
            overall_status = self.PENDING
        elif counts[Job.PENDING] + counts[Job.IN_PROGRESS] > 0:
            # Some units haven't finished yet, so the job isn't done yet
            overall_status = self.IN_PROGRESS
        else:
            # Job is done
            overall_status = self.DONE

        return dict(
            overall_status=overall_status,
            pending_units=counts[Job.PENDING],
            in_progress_units=counts[Job.IN_PROGRESS],
            failure_units=counts[Job.FAILURE],
            success_units=counts[Job.SUCCESS],
            total_units=total_unit_count,
        )


class ApiJobUnit(models.Model):
    """
    A smaller unit of work within an ApiJob.
    """
    # The larger ApiJob that this unit is a part of.
    parent = models.ForeignKey(ApiJob, on_delete=models.CASCADE)

    # Whether this is the 1st unit, 2nd unit, etc. for the parent ApiJob.
    order_in_parent = models.PositiveIntegerField()

    # The internal async Job which this unit basically proxies to
    # for several fields.
    internal_job = models.OneToOneField(Job, on_delete=models.PROTECT)

    @property
    def status(self):
        return self.internal_job.status

    def get_status_display(self):
        return self.internal_job.get_status_display()

    @property
    def result_message(self):
        return self.internal_job.result_message

    @property
    def create_date(self):
        return self.internal_job.create_date

    @property
    def modify_date(self):
        return self.internal_job.modify_date

    # JSON containing data on the requested work. The exact format depends
    # on the type of job unit.
    request_json = models.JSONField()

    # JSON results of the job unit when it's done. The exact format depends
    # on the type of job unit.
    result_json = models.JSONField(null=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                name="unique_order_within_parent",
                fields=['parent', 'order_in_parent']),
        ]
