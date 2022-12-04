from datetime import timedelta
from unittest import mock

from django.contrib.auth.models import User
from django.core import mail
from django.db import connections, transaction
from django.db.utils import DEFAULT_DB_ALIAS, load_backend
from django.test.testcases import TransactionTestCase
from django.test.utils import patch_logger
from django.utils import timezone

from api_core.models import ApiJob, ApiJobUnit
from errorlogs.tests.utils import ErrorReportTestMixin
from lib.tests.utils import BaseTest
from .exceptions import JobError
from .models import Job
from .tasks import clean_up_old_jobs, report_stuck_jobs
from .utils import (
    finish_job, full_job, job_runner,
    job_starter, queue_job, start_pending_job)


class QueueJobTest(BaseTest):

    def test_queue_job_when_already_pending(self):
        queue_job('name', 'arg')

        with patch_logger('jobs.utils', 'info') as log_messages:
            queue_job('name', 'arg')

            log_message = (
                f"Job [name / arg] is already pending or in progress."
            )
            self.assertIn(
                log_message, log_messages,
                "Should log the appropriate message")

        self.assertEqual(
            Job.objects.all().count(),
            1,
            "Should not have queued the second job")

    def test_queue_job_when_already_in_progress(self):
        queue_job('name', 'arg', initial_status=Job.IN_PROGRESS)

        with patch_logger('jobs.utils', 'info') as log_messages:
            queue_job('name', 'arg')

            log_message = (
                f"Job [name / arg] is already pending or in progress."
            )
            self.assertIn(
                log_message, log_messages,
                "Should log the appropriate message")

        self.assertEqual(
            Job.objects.all().count(),
            1,
            "Should not have queued the second job")

    def test_queue_job_when_previously_done(self):
        queue_job('name', 'arg', initial_status=Job.SUCCESS)
        queue_job('name', 'arg')

        self.assertEqual(
            Job.objects.all().count(),
            2,
            "Should have queued the second job")

    def test_attempt_number_increment(self):
        job = queue_job('name', 'arg', initial_status=Job.FAILURE)
        job.error_message = "An error"
        job.save()

        job_2 = queue_job('name', 'arg')

        self.assertEqual(
            job_2.attempt_number,
            2,
            "Should have attempt number of 2")

    def test_attempt_number_non_increment(self):
        queue_job('name', 'arg', initial_status=Job.SUCCESS)
        job_2 = queue_job('name', 'arg')

        self.assertEqual(
            job_2.attempt_number,
            1,
            "Should have attempt number of 1")


class StartPendingJobTest(BaseTest):

    def test_job_not_found(self):
        with patch_logger('jobs.utils', 'info') as log_messages:
            start_pending_job('name', 'arg')

            log_message = (
                f"Job [name / arg] not found."
            )
            self.assertIn(
                log_message, log_messages,
                "Should log the appropriate message")

    def test_job_already_in_progress(self):
        queue_job('name', 'arg', initial_status=Job.IN_PROGRESS)

        with patch_logger('jobs.utils', 'info') as log_messages:
            start_pending_job('name', 'arg')

            log_message = (
                f"Job [name / arg] already in progress."
            )
            self.assertIn(
                log_message, log_messages,
                "Should log the appropriate message")

    def test_delete_duplicate_jobs(self):
        queue_job('name', 'arg')
        for _ in range(5):
            Job(
                job_name='name',
                arg_identifier='arg',
            ).save()
        self.assertEqual(Job.objects.count(), 6)

        start_pending_job('name', 'arg')
        self.assertEqual(
            Job.objects.count(), 1,
            "Dupe jobs should have been deleted")


class FinishJobTest(BaseTest, ErrorReportTestMixin):

    def test_repeated_failure(self):
        # 4 fails in a row
        for _ in range(4):
            job = queue_job('name', 'arg', initial_status=Job.IN_PROGRESS)
            finish_job(job, error_message="An error")
            self.assert_no_email()

        # 5th fail in a row
        job = queue_job('name', 'arg', initial_status=Job.IN_PROGRESS)
        finish_job(job, error_message="An error")
        self.assert_error_email(
            "Job is failing repeatedly: name / arg",
            ["Currently on attempt number 5. Error:\n\nAn error"],
        )


@full_job()
def full_job_example(arg1):
    if arg1 == 'job_error':
        raise JobError("A JobError")
    if arg1 == 'other_error':
        raise ValueError("A ValueError")


@job_runner()
def job_runner_example(arg1):
    if arg1 == 'job_error':
        raise JobError("A JobError")
    if arg1 == 'other_error':
        raise ValueError("A ValueError")


@job_starter()
def job_starter_example(arg1):
    if arg1 == 'job_error':
        raise JobError("A JobError")
    if arg1 == 'other_error':
        raise ValueError("A ValueError")


class JobDecoratorTest(BaseTest, ErrorReportTestMixin):

    def test_full_completion(self):
        full_job_example('some_arg')
        job = Job.objects.latest('pk')

        self.assertEqual(job.job_name, 'full_job_example')
        self.assertEqual(job.arg_identifier, 'some_arg')
        self.assertEqual(job.status, Job.SUCCESS)
        self.assertEqual(job.error_message, "")

    def test_full_job_error(self):
        full_job_example('job_error')
        job = Job.objects.latest('pk')

        self.assertEqual(job.status, Job.FAILURE)
        self.assertEqual(job.error_message, "A JobError")
        self.assert_no_error_log_saved()
        self.assert_no_email()

    def test_full_other_error(self):
        full_job_example('other_error')
        job = Job.objects.latest('pk')

        self.assertEqual(job.status, Job.FAILURE)
        self.assertEqual(job.error_message, "A ValueError")

        self.assert_error_log_saved(
            "ValueError",
            "A ValueError",
        )
        self.assert_error_email(
            "Error in task: full_job_example",
            ["ValueError: A ValueError"],
        )

    def test_runner_completion(self):
        job = queue_job('job_runner_example', 'some_arg')

        job_runner_example('some_arg')
        job.refresh_from_db()

        self.assertEqual(job.job_name, 'job_runner_example')
        self.assertEqual(job.arg_identifier, 'some_arg')
        self.assertEqual(job.status, Job.SUCCESS)
        self.assertEqual(job.error_message, "")

    def test_runner_job_error(self):
        job = queue_job('job_runner_example', 'job_error')

        job_runner_example('job_error')
        job.refresh_from_db()

        self.assertEqual(job.status, Job.FAILURE)
        self.assertEqual(job.error_message, "A JobError")
        self.assert_no_error_log_saved()
        self.assert_no_email()

    def test_runner_other_error(self):
        job = queue_job('job_runner_example', 'other_error')

        job_runner_example('other_error')
        job.refresh_from_db()

        self.assertEqual(job.status, Job.FAILURE)
        self.assertEqual(job.error_message, "A ValueError")

        self.assert_error_log_saved(
            "ValueError",
            "A ValueError",
        )
        self.assert_error_email(
            "Error in task: job_runner_example",
            ["ValueError: A ValueError"],
        )

    def test_starter_progression(self):
        job = queue_job('job_starter_example', 'some_arg')

        job_starter_example('some_arg')
        job.refresh_from_db()

        self.assertEqual(job.job_name, 'job_starter_example')
        self.assertEqual(job.arg_identifier, 'some_arg')
        self.assertEqual(job.status, Job.IN_PROGRESS)
        self.assertEqual(job.error_message, "")

    def test_starter_job_error(self):
        job = queue_job('job_starter_example', 'job_error')

        job_starter_example('job_error')
        job.refresh_from_db()

        self.assertEqual(job.status, Job.FAILURE)
        self.assertEqual(job.error_message, "A JobError")
        self.assert_no_error_log_saved()
        self.assert_no_email()

    def test_starter_other_error(self):
        job = queue_job('job_starter_example', 'other_error')

        job_starter_example('other_error')
        job.refresh_from_db()

        self.assertEqual(job.status, Job.FAILURE)
        self.assertEqual(job.error_message, "A ValueError")

        self.assert_error_log_saved(
            "ValueError",
            "A ValueError",
        )
        self.assert_error_email(
            "Error in task: job_starter_example",
            ["ValueError: A ValueError"],
        )


def save_two_copies(self, *args, **kwargs):
    # Must use the 2-arg super() form when using super() in a
    # function defined outside of a class.
    super(Job, self).save(*args, **kwargs)
    self.pk = None
    super(Job, self).save(*args, **kwargs)


class JobStartRaceConditionTest(TransactionTestCase):
    """
    This test class involves the locking behavior of
    select_for_update(), which is why we must base off of
    TransactionTestCase instead of TestCase.
    https://docs.djangoproject.com/en/4.1/topics/testing/tools/#transactiontestcase
    """

    @staticmethod
    def create_connection(alias=DEFAULT_DB_ALIAS):
        """
        TODO: This method can likely be replaced by
         django.db.connections.create_connection() starting around Django 3.2.
         https://github.com/django/django/commit/98e05ccde440cc9b768952cc10bc8285f4924e1f#diff-76917634c6c088f56f8dec9493294c657953e61b01e38e33b02d876d5e96dd3a
        """
        connections.ensure_defaults(alias)
        connections.prepare_test_settings(alias)
        db = connections.databases[alias]
        backend = load_backend(db['ENGINE'])
        return backend.DatabaseWrapper(db, alias)

    def test_start_pending_job(self):
        # Create a pending job.
        queue_job('name', 'arg')

        # Prepare a select-for-update query which includes that job.
        queryset = Job.objects \
            .filter(job_name='name') \
            .select_for_update(nowait=True)

        # Get the query's SQL. We don't particularly need to execute the
        # query here, but in the process of getting the SQL, it does get
        # executed. Since it's a select-for-update, a transaction is
        # required.
        with transaction.atomic():
            queryset_sql = \
                queryset.query.sql_with_params()[0] % "'name'"

        # Make an extra DB connection.
        connection = self.create_connection()
        try:
            # Start a transaction with the extra DB connection.
            # We do it this way because transaction.atomic() would only
            # apply to the default connection.
            connection.set_autocommit(False)

            # With the extra DB connection, query the job row with
            # select_for_update(). This should lock the row for update
            # for the duration of the connection's transaction.
            with connection.cursor() as c:
                c.execute(queryset_sql)

            # With the default DB connection, make a start_pending_job() call
            # which will query the same row. Should get locked out.
            with patch_logger('jobs.utils', 'info') as log_messages:
                start_pending_job('name', 'arg')

                log_message = (
                    f"Job [name / arg] is locked"
                    f" to prevent overlapping runs."
                )
                self.assertIn(
                    log_message, log_messages,
                    "Should log the appropriate message")
        finally:
            # Close the extra DB connection.
            connection.close()

    def test_queue_in_progress_job(self):
        # Try to queue two in-progress jobs of the same name/args.
        # To simulate the race condition, we've mocked Job.save()
        # to create two identical jobs instead of just one job.
        with mock.patch.object(Job, 'save', save_two_copies):
            with patch_logger('jobs.utils', 'info') as log_messages:
                queue_job('name', 'arg', initial_status=Job.IN_PROGRESS)

                log_message = (
                    f"Job [name / arg] is already in progress."
                )
                self.assertIn(
                    log_message, log_messages,
                    "Should log the appropriate message")


class CleanupTaskTest(BaseTest):

    def test_date_based_selection(self):
        """
        Jobs should be selected for cleanup based on date.
        """
        # More than one job too new to be cleaned up.

        queue_job('new')

        job = queue_job('29 days ago')
        # Use QuerySet.update() instead of Model.save() so that the modify
        # date doesn't get auto-updated to the current date.
        Job.objects.filter(pk=job.pk).update(
            modify_date=timezone.now() - timedelta(days=29))

        # More than one job old enough to be cleaned up.

        job = queue_job('31 days ago')
        Job.objects.filter(pk=job.pk).update(
            modify_date=timezone.now() - timedelta(days=31))

        job = queue_job('32 days ago')
        Job.objects.filter(pk=job.pk).update(
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
