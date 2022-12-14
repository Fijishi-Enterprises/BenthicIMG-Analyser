from datetime import timedelta
from unittest import mock

from django.contrib.auth.models import User
from django.core import mail
from django.test.utils import override_settings, patch_logger
from django.utils import timezone

from api_core.models import ApiJob, ApiJobUnit
from lib.tests.utils import BaseTest
from ..models import Job
from ..tasks import clean_up_old_jobs, report_stuck_jobs, run_scheduled_jobs
from ..utils import queue_job
from .utils import queue_job_with_modify_date


def call_run_scheduled_jobs():
    run_scheduled_jobs()
    return []


class RunScheduledJobsTest(BaseTest):

    def test_no_multiple_runs(self):
        """
        Should block multiple existing runs of this task. That way, no job
        looped through in this task can get started in celery multiple times.
        """
        with patch_logger('jobs.utils', 'debug') as log_messages:

            # Mock a function called by the task, and make that function
            # attempt to run the task recursively.
            with mock.patch(
                'jobs.tasks.get_scheduled_jobs', call_run_scheduled_jobs
            ):
                run_scheduled_jobs()

            log_message = (
                "Job [run_scheduled_jobs / ]"
                " is already pending or in progress."
            )
            self.assertIn(
                log_message, log_messages,
                "Should log the appropriate message")

        self.assertEqual(
            Job.objects.filter(job_name='run_scheduled_jobs').count(), 1,
            "Should not have accepted the second run")


@override_settings(JOB_MAX_DAYS=30)
class CleanupTaskTest(BaseTest):

    def test_date_based_selection(self):
        """
        Jobs should be selected for cleanup based on date.
        """
        # More than one job too new to be cleaned up.
        queue_job('new')
        queue_job_with_modify_date(
            '29 days ago',
            modify_date=timezone.now() - timedelta(days=29))

        # More than one job old enough to be cleaned up.
        queue_job_with_modify_date(
            '31 days ago',
            modify_date=timezone.now() - timedelta(days=31))
        queue_job_with_modify_date(
            '32 days ago',
            modify_date=timezone.now() - timedelta(days=32))

        clean_up_old_jobs()

        self.assertTrue(
            Job.objects.filter(job_name='new').exists(),
            "Shouldn't clean up new job")
        self.assertTrue(
            Job.objects.filter(job_name='29 days ago').exists(),
            "Shouldn't clean up 29 day old job")
        self.assertFalse(
            Job.objects.filter(job_name='31 days ago').exists(),
            "Should clean up 31 day old job")
        self.assertFalse(
            Job.objects.filter(job_name='32 days ago').exists(),
            "Should clean up 32 day old job")

    def test_unit_presence_based_selection(self):
        """
        Jobs associated with an existing ApiJobUnit should not be
        cleaned up.
        """
        user = User(username='some_user')
        user.save()
        api_job = ApiJob(type='', user=user)
        api_job.save()

        job = queue_job('unit 1')
        ApiJobUnit(
            parent=api_job, internal_job=job,
            order_in_parent=1, request_json=[]).save()

        queue_job('no unit')

        job = queue_job('unit 2')
        ApiJobUnit(
            parent=api_job, internal_job=job,
            order_in_parent=2, request_json=[]).save()

        # Make all jobs old enough to be cleaned up
        Job.objects.update(
            modify_date=timezone.now() - timedelta(days=32))

        clean_up_old_jobs()

        self.assertTrue(
            Job.objects.filter(job_name='unit 1').exists(),
            "Shouldn't clean up unit 1's job")
        self.assertTrue(
            Job.objects.filter(job_name='unit 2').exists(),
            "Shouldn't clean up unit 2's job")
        self.assertFalse(
            Job.objects.filter(job_name='no unit').exists(),
            "Should clean up no-unit job")


class ReportStuckJobsTest(BaseTest):
    """
    Test the report_stuck_jobs task.
    """
    @staticmethod
    def create_job(name, arg, modify_date, status=Job.PENDING):
        job = Job.objects.create(
            job_name=name, arg_identifier=arg, status=status)
        job.save()
        Job.objects.filter(pk=job.pk).update(modify_date=modify_date)
        return job.pk

    def test_job_selection_by_date(self):
        """
        Only warn about jobs between 3 and 4 days old, and warn once per job.
        """
        self.create_job(
            '1', '2d 23h ago',
            timezone.now() - timedelta(days=2, hours=23))

        self.create_job(
            '2', '3d 1h ago',
            timezone.now() - timedelta(days=3, hours=1))

        self.create_job(
            '3', '3d 23h ago',
            timezone.now() - timedelta(days=3, hours=23))

        self.create_job(
            '4', '4d 1h ago',
            timezone.now() - timedelta(days=4, hours=1))

        report_stuck_jobs()

        self.assertEqual(len(mail.outbox), 1)
        sent_email = mail.outbox[0]

        self.assertEqual(
            "[CoralNet] 2 job(s) haven't progressed in 3 days",
            sent_email.subject)
        self.assertEqual(
            "The following job(s) haven't progressed in 3 days:"
            "\n"
            f"\n2 / 3d 1h ago"
            f"\n3 / 3d 23h ago",
            sent_email.body)

    def test_job_selection_by_status(self):
        """
        Only warn about non-completed jobs.
        """
        d3h1 = timezone.now() - timedelta(days=3, hours=1)

        self.create_job('1', 'PENDING', d3h1, status=Job.PENDING)
        self.create_job('2', 'SUCCESS', d3h1, status=Job.SUCCESS)
        self.create_job('3', 'IN_PROGRESS', d3h1, status=Job.IN_PROGRESS)
        self.create_job('4', 'FAILURE', d3h1, status=Job.FAILURE)

        report_stuck_jobs()

        self.assertEqual(len(mail.outbox), 1)
        sent_email = mail.outbox[0]

        self.assertEqual(
            "[CoralNet] 2 job(s) haven't progressed in 3 days",
            sent_email.subject)
        self.assertEqual(
            "The following job(s) haven't progressed in 3 days:"
            "\n"
            f"\n1 / PENDING"
            f"\n3 / IN_PROGRESS",
            sent_email.body)
