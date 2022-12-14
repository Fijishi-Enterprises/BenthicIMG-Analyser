from unittest.case import TestCase

from ..models import Job
from ..utils import queue_job


def queue_job_with_modify_date(*args, modify_date=None, **kwargs):
    job = queue_job(*args, **kwargs)

    # Use QuerySet.update() instead of Model.save() so that the modify
    # date doesn't get auto-updated to the current date.
    Job.objects.filter(pk=job.pk).update(modify_date=modify_date)

    return job


class JobUtilsMixin(TestCase):

    def assert_job_result_message(self, job_name, expected_message):
        job = Job.objects.filter(job_name=job_name).latest('pk')
        self.assertEqual(
            job.result_message, expected_message,
            "Job result message should be as expected"
        )
