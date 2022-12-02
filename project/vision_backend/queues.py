import abc
from collections import Counter
from datetime import timedelta
from io import StringIO
import json
import logging
import sys
import time
from typing import Generator

import boto3
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.files.storage import get_storage_class
from django.utils import timezone
from django.utils.module_loading import import_string
from spacer.messages import JobMsg, JobReturnMsg
from spacer.tasks import process_job

from jobs.models import Job
from jobs.utils import finish_job
from .models import BatchJob
from .task_helpers import job_token_to_task_args

logger = logging.getLogger(__name__)


def get_queue_class():
    """This function is modeled after Django's get_storage_class()."""

    if (
        settings.SPACER_QUEUE_CHOICE ==
        'vision_backend.queues.BatchQueue'
        and
        settings.DEFAULT_FILE_STORAGE ==
        'lib.storage_backends.MediaStorageLocal'
        and
        'test' not in sys.argv
    ):
        # We only raise this in non-test environments, because some tests
        # are able to use mocks to test BatchQueue while sticking with
        # local storage.
        raise ImproperlyConfigured(
            "Can not use Remote queue with local storage."
            " Please use S3 storage."
        )

    return import_string(settings.SPACER_QUEUE_CHOICE)


class BaseQueue(abc.ABC):

    status_counts = None

    @abc.abstractmethod
    def submit_job(self, job: JobMsg):
        raise NotImplementedError

    @abc.abstractmethod
    def collect_jobs(self) -> Generator[JobReturnMsg, None, None]:
        """
        Check the entire job queue. Collect any completed jobs,
        and yield the result of each successfully-completed job.
        """
        raise NotImplementedError


def get_batch_client():
    return boto3.client(
        'batch',
        region_name="us-west-2",
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY
    )


class BatchQueue(BaseQueue):
    """
    Manages AWS Batch jobs.
    """

    @staticmethod
    def get_job_name(job_msg: JobMsg):
        """ This gives the job a unique name. It can be useful when browsing
        the AWS Batch console. However, it's only for humans. The actual
        mapping is encoded in the BatchJobs table."""
        return settings.SPACER_JOB_HASH + '-' + \
            job_msg.task_name + '-' + \
            '-'.join([t.job_token for t in job_msg.tasks])

    def submit_job(self, job_msg: JobMsg):

        batch_client = get_batch_client()
        storage = get_storage_class()()

        batch_job = BatchJob(job_token=self.get_job_name(job_msg))
        batch_job.save()

        job_msg_loc = storage.spacer_data_loc(batch_job.job_key)
        job_msg.store(job_msg_loc)

        job_res_loc = storage.spacer_data_loc(batch_job.res_key)

        resp = batch_client.submit_job(
            jobQueue=settings.BATCH_QUEUE,
            jobName=str(batch_job.pk),
            jobDefinition=settings.BATCH_JOB_DEFINITION,
            containerOverrides={
                'environment': [
                    {
                        'name': 'JOB_MSG_LOC',
                        'value': json.dumps(job_msg_loc.serialize()),
                    },
                    {
                        'name': 'RES_MSG_LOC',
                        'value': json.dumps(job_res_loc.serialize()),
                    },
                ],
            }
        )
        batch_job.batch_token = resp['jobId']
        batch_job.save()

    @staticmethod
    def handle_job_failure(batch_job, error_message):
        batch_job.status = 'FAILED'
        batch_job.save()

        storage = get_storage_class()()
        job_msg_loc = storage.spacer_data_loc(batch_job.job_key)
        job_msg = JobMsg.load(job_msg_loc)

        for task in job_msg.tasks:
            # Get the associated Job instances and update them.
            job_args = job_token_to_task_args(
                job_msg.task_name, task.job_token)
            job = Job.objects.get(
                job_name=job_msg.task_name,
                arg_identifier=Job.args_to_identifier(job_args))
            # Mark it as failed.
            finish_job(job, error_message=error_message)

    def collect_jobs(self):
        job_statuses = []

        batch_client = get_batch_client()
        storage = get_storage_class()()

        # Iterate over not-yet-collected BatchJobs.
        for job in BatchJob.objects.exclude(
            status__in=['SUCCEEDED', 'FAILED']
        ):

            if job.batch_token is None:
                # Didn't get a batch token from AWS Batch. May indicate AWS
                # service problems (see coralnet issue 458) or it may just be
                # unlucky timing between submit and collect. Check the
                # create_date to be sure.
                if timezone.now() - job.create_date > timedelta(minutes=30):
                    # Likely an AWS service problem.
                    self.handle_job_failure(
                        job, "Failed to get AWS Batch token.")
                    job_statuses.append('DROPPED')
                else:
                    # Let's wait a bit longer.
                    job_statuses.append('NOT SUBMITTED')
                # In either case, continue to next job.
                continue

            resp = batch_client.describe_jobs(jobs=[job.batch_token])

            if len(resp['jobs']) == 0:
                self.handle_job_failure(
                    job, f"Batch job [{job}] not found in AWS.")
                job_statuses.append('DROPPED')
                continue

            job.status = resp['jobs'][0]['status']
            job.save()

            if job.status == 'FAILED':
                self.handle_job_failure(
                    job, f"Batch job [{job}] marked as FAILED by AWS.")

            elif job.status == 'SUCCEEDED':
                logger.info(f"Entering collection of Batch job [{job}].")
                job_res_loc = storage.spacer_data_loc(job.res_key)

                try:
                    return_msg = JobReturnMsg.load(job_res_loc)
                except IOError as e:
                    self.handle_job_failure(
                        job,
                        f"Batch job [{job}] succeeded,"
                        f" but couldn't get output at the expected location."
                        f" ({e})")
                else:
                    # Success
                    logger.info(f"Exiting collection of Batch job [{job}].")
                    yield return_msg

            job_statuses.append(job.status)

        # Count the job statuses
        self.status_counts = Counter(job_statuses)


class LocalQueue(BaseQueue):
    """
    Used for testing the vision-backend Django tasks.
    Uses a local filesystem queue and calls spacer directly.
    """

    def submit_job(self, job: JobMsg):

        # Process the job right away.
        return_msg = process_job(job)

        storage = get_storage_class()()

        # Save as seconds.microseconds to avoid collisions.
        filepath = storage.path_join('backend_job_res', f'{time.time()}.json')
        storage.save(
            filepath,
            StringIO(json.dumps(return_msg.serialize())))

    def collect_jobs(self):
        job_statuses = []

        storage = get_storage_class()()
        try:
            dir_names, filenames = storage.listdir('backend_job_res')
        except FileNotFoundError:
            # Perhaps this is a test run and no results files were created
            # yet (thus, the backend_job_res directory was not created).
            filenames = []

        # Sort by filename, which should also put them in job order
        # because the filenames have timestamps (to microsecond precision)
        filenames.sort()

        for filename in filenames:

            # Read the job result message
            filepath = storage.path_join('backend_job_res', filename)
            with storage.open(filepath) as results_file:
                return_msg = JobReturnMsg.deserialize(json.load(results_file))
            # Delete the job result file
            storage.delete(filepath)

            yield return_msg

            # Unlike BatchQueue, LocalQueue is only aware of the
            # jobs that successfully output their results.
            job_statuses.append('SUCCEEDED')

        # Count the job statuses
        self.status_counts = Counter(job_statuses)
