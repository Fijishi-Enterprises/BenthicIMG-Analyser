import re
from typing import Union
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

    job.refresh_from_db()
    return job


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

    job.refresh_from_db()
    return job


def do_job(name, *task_args, **kwargs):
    """
    Sometimes we don't care if a job was already queued or not. Just run it
    if it exists, and if not, queue it then run it.
    This does assume that said job is not already running (must either be
    pending or not exist yet).
    """
    job = queue_job(name, *task_args, **kwargs)
    if job:
        run_job(job)
    else:
        job = run_pending_job(name, Job.args_to_identifier(task_args))

    job.refresh_from_db()
    return job


class JobUtilsMixin(TestCase):

    def assert_job_persist_value(self, job_name, expected_value):
        job = Job.objects.filter(job_name=job_name).latest('pk')
        self.assertEqual(
            job.persist, expected_value,
            "Job persist value should be as expected"
        )

    def assert_job_result_message(
        self, job_name,
        expected_message: Union[str, re.Pattern],
        assert_msg="Job result message should be as expected",
    ):
        job = Job.objects.filter(job_name=job_name).latest('pk')

        if isinstance(expected_message, re.Pattern):
            self.assertRegex(
                job.result_message, expected_message, msg=assert_msg,
            )
        else:
            self.assertEqual(
                job.result_message, expected_message, msg=assert_msg,
            )

    def source_check_and_assert_message(
        self, expected_message, assert_msg=None,
    ):
        do_job('check_source', self.source.pk, source_id=self.source.pk)
        self.assert_job_result_message(
            'check_source', expected_message, assert_msg=assert_msg)
