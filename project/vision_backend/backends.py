import json
import logging
import posixpath
import random
from six import StringIO
import string
import time

import boto.sqs
from django.conf import settings
from django.core.files.storage import get_storage_class
from django.utils.module_loading import import_string

logger = logging.getLogger(__name__)


def get_backend_class():
    """This function is modeled after Django's get_storage_class()."""
    return import_string(settings.VISION_BACKEND_CHOICE)


class BaseBackend(object):

    def submit_job(self, messagebody):
        raise NotImplementedError

    def collect_job(self):
        raise NotImplementedError


class SpacerBackend(BaseBackend):
    """Communicates remotely with Spacer. Requires AWS SQS and S3."""

    def submit_job(self, messagebody):
        """
        Submits message to the SQS spacer_jobs
        """
        messagebody['payload']['bucketname'] = settings.AWS_STORAGE_BUCKET_NAME

        conn = boto.sqs.connect_to_region("us-west-2",
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY)
        queue = conn.get_queue('spacer_jobs')
        m = boto.sqs.message.Message()
        m.set_body(json.dumps(messagebody))
        queue.write(m)

    def collect_job(self):
        """
        If an AWS SQS job result is available, collect it, delete from queue
        if it's a job for this server instance, and return it.
        Else, return None.
        """

        # Grab a message
        message = self._read_message('spacer_results')
        if message is None:
            return None
        messagebody = json.loads(message.get_body())

        # Check that the message pertains to this server
        if not messagebody['original_job']['payload']['bucketname'] == settings.AWS_STORAGE_BUCKET_NAME:
            logger.info("Job pertains to wrong bucket [%]".format(messagebody['original_job']['payload']['bucketname']))
            return messagebody

        # Delete message (at this point, if it is not handled correctly, we still want to delete it from queue.)
        message.delete()

        return messagebody

    def _read_message(self, queue_name):
        """
        helper function for reading messages from AWS SQS.
        """

        conn = boto.sqs.connect_to_region("us-west-2",
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY)

        queue = conn.get_queue(queue_name)

        message = queue.read()
        if message is None:
            return None
        else:
            return message


class MockBackend(BaseBackend):
    """
    Used for testing the vision-backend Django tasks.
    Does not actually use expensive computer vision algorithms; the focus is
    on returning results in the right formats.
    Uses either local or S3 file storage.
    """
    def submit_job(self, messagebody):
        """Consume the job right here, and write a result to file storage."""
        if messagebody['task'] == 'extract_features':
            job_result = self._extract_features(messagebody)
        elif messagebody['task'] == 'train_classifier':
            job_result = self._train_classifier(messagebody)
        else:
            raise ValueError(
                "Unsupported task: {task}".format(task=messagebody['task']))

        storage = get_storage_class()()
        # Taking some care to avoid filename collisions.
        attempts = 5
        for attempt_number in range(1, attempts+1):
            try:
                filepath = 'backend_job_results/{timestamp}_{random_str}.json'.format(
                    timestamp=int(time.time()),
                    random_str=''.join(
                        [random.choice(string.ascii_lowercase)
                        for _ in range(10)]),
                )
                storage.save(filepath, StringIO(json.dumps(job_result)))
                break
            except IOError as e:
                if attempt_number == attempts:
                    # Final attempt failed
                    raise e

    def collect_job(self):
        """
        Read a job result from file storage, consume (delete) it,
        and return it. If no result is available, return None.
        """
        storage = get_storage_class()()
        dir_names, filenames = storage.listdir('backend_job_results')

        if len(filenames) == 0:
            return None

        # Sort by filename, which should also put them in job order
        # because the filenames have timestamps (to second precision)
        filenames.sort()
        # Get the first job result file, so it's like a queue
        filename = filenames[0]
        # Read the job result message
        filepath = posixpath.join('backend_job_results', filename)
        with storage.open(filepath) as results_file:
            messagebody = json.load(results_file)
        # Delete the job result file
        storage.delete(filepath)

        return messagebody

    def _extract_features(self, original_job):
        # TODO: Actually create a features file

        messagebody = dict(
            original_job=original_job,
            result=dict(
                runtime=dict(
                    total=1,
                    core=2,
                ),
                model_was_cashed=False,
            ),
        )
        return messagebody

    def _train_classifier(self, original_job):
        # TODO: Actually create a model file and a valresult file

        messagebody = dict(
            original_job=original_job,
            result=dict(
                ok=True,
                runtime=1,
                acc=2,
                refacc=[3, 4],
                pc_accs=5,
            ),
        )
        return messagebody
