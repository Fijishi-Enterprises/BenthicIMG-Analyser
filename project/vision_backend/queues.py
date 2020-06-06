import abc
import json
import logging
import posixpath
import time

import boto.sqs
from django.conf import settings
from django.core.files.storage import get_storage_class
from django.utils.module_loading import import_string
from six import StringIO
from spacer.messages import JobMsg, JobReturnMsg
from spacer.tasks import process_job

logger = logging.getLogger(__name__)


def get_queue_class():
    """This function is modeled after Django's get_storage_class()."""
    return import_string(settings.VISION_BACKEND_CHOICE)


class BaseQueue(abc.ABC):

    @abc.abstractmethod
    def submit_job(self, job: JobMsg):
        pass

    @abc.abstractmethod
    def collect_job(self) -> JobReturnMsg:
        pass


class SQSQueue(BaseQueue):
    """Communicates remotely with Spacer. Requires AWS SQS and S3."""

    def submit_job(self, job: JobMsg):
        """
        Submits message to the SQS spacer_jobs
        """
        conn = boto.sqs.connect_to_region(
            "us-west-2",
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY
        )
        queue = conn.get_queue(settings.SQS_JOBS)
        msg = queue.new_message(body=json.dumps(job.serialize()))
        queue.write(msg)

    def collect_job(self):
        """
        If an AWS SQS job result is available, collect it, delete from queue
        if it's a job for this server instance, and return it.
        Else, return None.
        """

        # Grab a message
        message = self._read_message(settings.SQS_RES)
        if message is None:
            return None

        return_msg = JobReturnMsg.deserialize(json.loads(message.get_body()))

        # Check that the message pertains to this server
        if settings.SPACER_JOB_HASH not in \
                return_msg.original_job.tasks[0].job_token:
            logger.info("Job has doesn't match")
            return None

        # Delete message (at this point, if it is not handled correctly,
        # we still want to delete it from queue.)
        message.delete()

        return return_msg

    @staticmethod
    def _read_message(queue_name):
        """
        helper function for reading messages from AWS SQS.
        """

        conn = boto.sqs.connect_to_region(
            "us-west-2",
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY
        )

        queue = conn.get_queue(queue_name)

        message = queue.read()
        if message is None:
            return None
        else:
            return message


class MockQueue(BaseQueue):
    """
    Used for testing the vision-backend Django tasks.
    Uses a mock queue and calls spacer directly.
    """
    def submit_job(self, job: JobMsg):

        # Process the job right away.
        return_msg = process_job(job)

        storage = get_storage_class()()

        # Save as seconds.microseconds to avoid collisions.
        filepath = 'backend_job_res/{timestamp}.json'.\
            format(timestamp=time.time())
        storage.save(filepath, StringIO(json.dumps(return_msg.serialize())))

    def collect_job(self):
        """
        Read a job result from file storage, consume (delete) it,
        and return it. If no result is available, return None.
        """
        storage = get_storage_class()()
        dir_names, filenames = storage.listdir('backend_job_res')

        if len(filenames) == 0:
            return None

        # Sort by filename, which should also put them in job order
        # because the filenames have timestamps (to second precision)
        filenames.sort()
        # Get the first job result file, so it's like a queue
        filename = filenames[0]
        # Read the job result message
        filepath = posixpath.join('backend_job_res', filename)
        with storage.open(filepath) as results_file:
            return_msg = JobReturnMsg.deserialize(json.load(results_file))
        # Delete the job result file
        storage.delete(filepath)

        return return_msg
