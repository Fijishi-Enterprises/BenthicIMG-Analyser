from datetime import timedelta
import logging
import random
import sys
import traceback
from typing import Optional

from django.core.mail import mail_admins
from django.db import DatabaseError, IntegrityError, transaction
from django.utils import timezone
from django.views.debug import ExceptionReporter

from errorlogs.utils import instantiate_error_log
from .exceptions import JobError
from .models import Job

logger = logging.getLogger(__name__)


def queue_job(
        name: str,
        *task_args,
        delay: timedelta = None,
        source_id: int = None,
        initial_status: str = Job.PENDING) -> Optional[Job]:

    if delay is None:
        # Use a random amount of jitter to slightly space out jobs that are
        # being submitted in quick succession.
        delay = timedelta(seconds=random.randrange(5, 30))

    arg_identifier = Job.args_to_identifier(task_args)
    job_kwargs = dict(
        job_name=name,
        arg_identifier=arg_identifier,
    )

    # See if the same job is already pending or in progress. This is just a
    # best-effort check. We want this to be safe for views to call without
    # crashing the current transaction, which is why we don't make this
    # stricter against race conditions. We'll be stricter if actually
    # starting a job (as opposed to just queueing it as pending).
    jobs = Job.objects.filter(**job_kwargs)
    try:
        job = jobs.get(status__in=[Job.PENDING, Job.IN_PROGRESS])
    except Job.DoesNotExist:
        pass
    else:
        logger.debug(f"Job [{job}] is already pending or in progress.")
        return None

    # See if the same job failed last time (if there was a last time).
    # If so, set the attempt count accordingly.
    attempt_number = 1
    try:
        last_job = jobs.latest('pk')
    except Job.DoesNotExist:
        pass
    else:
        if last_job.status == Job.FAILURE:
            attempt_number = last_job.attempt_number + 1

    # Create a new job and proceed
    scheduled_start_date = timezone.now() + delay
    job = Job(
        scheduled_start_date=scheduled_start_date,
        attempt_number=attempt_number,
        source_id=source_id,
        status=initial_status,
        **job_kwargs
    )
    try:
        job.save()
    except IntegrityError:
        # There's a DB-level uniqueness check which prevents duplicate
        # in-progress jobs.
        # This ensures that we don't have two threads starting the same
        # job at the same time. (This works most effectively if we use
        # short transactions or autocommit when creating in-progress jobs.)
        logger.info(f"Job [{job}] is already in progress.")
        return None

    return job


def start_pending_job(job_name: str, arg_identifier: str) -> Optional[Job]:
    """
    Find a pending job matching the passed fields.
    If job not found, or already in progress, return None.
    Else, update the status to in-progress and return the job.
    """
    # select_for_update() locks these DB rows from evaluation time
    # to the end of the transaction. This ensures that we don't
    # have two threads starting the same job at the same time.
    # Instead, the first thread will get to run, while the second thread
    # will get a DatabaseError and return.
    # (This works most effectively if we're using autocommit when entering
    # this function.)
    jobs_queryset = Job.objects.select_for_update(nowait=True).filter(
        job_name=job_name,
        arg_identifier=arg_identifier,
        status__in=[Job.PENDING, Job.IN_PROGRESS],
    )
    with transaction.atomic():
        # Evaluate the query.
        try:
            jobs = list(jobs_queryset)
        except DatabaseError:
            # Probably tripped the select_for_update() row locking, meaning
            # there's another thread in here already.
            logger.info(
                f"Job [{job_name} / {arg_identifier}] is locked"
                f" to prevent overlapping runs.")
            return None

        if len(jobs) == 0:
            logger.info(f"Job [{job_name} / {arg_identifier}] not found.")
            return None

        if Job.IN_PROGRESS in [job.status for job in jobs]:
            logger.info(f"Job [{jobs[0]}] already in progress.")
            return None

        job = jobs[0]
        if len(jobs) > 1:
            for dupe_job in jobs[1:]:
                # Delete any duplicate pending jobs
                dupe_job.delete()

        job.status = Job.IN_PROGRESS
        job.save()
    return job


def finish_job(job, error_message=None):
    """
    Update Job status from IN_PROGRESS to SUCCESS/FAILURE,
    and do associated bookkeeping.
    """
    # This field doesn't take None; non-errors are set as an empty string.
    job.error_message = error_message or ""
    job.status = Job.FAILURE if error_message else Job.SUCCESS
    job.save()

    if job.status == Job.FAILURE and job.attempt_number % 5 == 0:
        mail_admins(
            f"Job is failing repeatedly:"
            f" {job.job_name} / {job.arg_identifier}",
            f"Currently on attempt number {job.attempt_number}. Error:"
            f"\n\n{error_message}",
        )


class JobDecorator:
    def __init__(self, job_name=None):
        self.job_name = job_name

    def __call__(self, task_func):
        raise NotImplementedError

    @staticmethod
    def report_task_error(task_func):
        # Get the most recent exception's info.
        kind, info, data = sys.exc_info()

        # Email admins.
        error_data = '\n'.join(traceback.format_exception(kind, info, data))
        mail_admins(
            f"Error in task: {task_func.__name__}",
            f"{kind.__name__}: {info}\n\n{error_data}",
        )

        # Save an ErrorLog.
        error_html = ExceptionReporter(
            None, kind, info, data).get_traceback_html()
        error_log = instantiate_error_log(
            kind=kind.__name__,
            html=error_html,
            path=f"Task - {task_func.__name__}",
            info=info,
            data=error_data,
        )
        error_log.save()


class FullJobDecorator(JobDecorator):
    """
    Job is created as IN_PROGRESS at the start of the decorated task,
    and goes IN_PROGRESS -> SUCCESS/FAILURE at the end of it.
    """
    def __call__(self, task_func):
        def task_wrapper(*task_args):
            job = queue_job(
                self.job_name or task_func.__name__,
                *task_args,
                delay=timedelta(seconds=0),
                initial_status=Job.IN_PROGRESS,
                # No usages are source-specific yet.
                source_id=None,
            )
            if not job:
                return

            error_message = None
            try:
                # Run the task function (which isn't a celery task itself;
                # the result of this wrapper should be registered as a
                # celery task).
                task_func(*task_args)
            except JobError as e:
                error_message = str(e)
            except Exception as e:
                # Non-JobError, likely needs fixing:
                # report it like a server error
                error_message = str(e)
                self.report_task_error(task_func)
            finally:
                # Regardless of error or not, mark job as done
                finish_job(job, error_message=error_message)

        return task_wrapper


full_job = FullJobDecorator


class JobRunnerDecorator(JobDecorator):
    """
    Job status goes PENDING -> IN_PROGRESS at the start of the
    decorated task, and IN_PROGRESS -> SUCCESS/FAILURE at the end of it.
    """
    def __call__(self, task_func):
        def task_wrapper(*task_args):
            job = start_pending_job(
                job_name=self.job_name or task_func.__name__,
                arg_identifier=Job.args_to_identifier(task_args),
            )
            if not job:
                return

            error_message = None
            try:
                task_func(*task_args)
            except JobError as e:
                error_message = str(e)
            except Exception as e:
                # Non-JobError, likely needs fixing:
                # report it like a server error
                error_message = str(e)
                self.report_task_error(task_func)
            finally:
                # Regardless of error or not, mark job as done
                finish_job(job, error_message=error_message)

        return task_wrapper


job_runner = JobRunnerDecorator


class JobStarterDecorator(JobDecorator):
    """
    Job status goes PENDING -> IN_PROGRESS at the start of the
    decorated task. No update is made at the end of the task.
    """
    def __call__(self, task_func):
        def task_wrapper(*task_args):
            job = start_pending_job(
                job_name=self.job_name or task_func.__name__,
                arg_identifier=Job.args_to_identifier(task_args),
            )
            if not job:
                return

            try:
                task_func(*task_args, job_id=job.pk)
            except JobError as e:
                # JobError: job is considered done
                finish_job(job, error_message=str(e))
            except Exception as e:
                # Non-JobError, likely needs fixing:
                # job is considered done, and report it like a server error
                self.report_task_error(task_func)
                finish_job(job, error_message=str(e))

        return task_wrapper


job_starter = JobStarterDecorator
