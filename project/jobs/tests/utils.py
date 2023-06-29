from unittest.case import TestCase

from ..models import Job
from ..utils import queue_job, run_job


def queue_job_with_modify_date(*args, modify_date=None, **kwargs):
    job = queue_job(*args, **kwargs)

    # Use QuerySet.update() instead of Model.save() so that the modify
    # date doesn't get auto-updated to the current date.
    Job.objects.filter(pk=job.pk).update(modify_date=modify_date)

    return job


def queue_and_run_job(*args, **kwargs):
    job = queue_job(*args, **kwargs)
    run_job(job)


def run_pending_job(job_name, arg_identifier):
    """
    Sometimes we want to run only a specific job without touching others
    that are pending.

    This is much less rigorous against race conditions etc. than
    start_pending_job(), and should only be used for testing.
    """
    job = Job.objects.get(
        job_name=job_name,
        arg_identifier=arg_identifier,
        status=Job.Status.PENDING,
    )
    run_job(job)


class JobUtilsMixin(TestCase):

    def assert_job_persist_value(self, job_name, expected_value):
        job = Job.objects.filter(job_name=job_name).latest('pk')
        self.assertEqual(
            job.persist, expected_value,
            "Job persist value should be as expected"
        )

    def assert_job_result_message(self, job_name, expected_message):
        job = Job.objects.filter(job_name=job_name).latest('pk')
        self.assertEqual(
            job.result_message, expected_message,
            "Job result message should be as expected"
        )
