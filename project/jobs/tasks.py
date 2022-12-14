from datetime import timedelta
import logging

from celery.decorators import periodic_task
from django.conf import settings
from django.core.mail import mail_admins
from django.utils import timezone

from vision_backend.tasks import (
    check_source, classify_image, deploy, submit_classifier, submit_features)
from .models import Job
from .utils import full_job

logger = logging.getLogger(__name__)


# Each Job is assumed to start with a Celery task. It doesn't necessarily
# have to finish at the end of that same task.
# For lack of more clever solutions, we'll map from job names to
# starter tasks here.
job_starter_tasks = {
    'check_source': check_source,
    'classify_features': classify_image,
    'classify_image': deploy,
    'train_classifier': submit_classifier,
    'extract_features': submit_features,
}


def get_scheduled_jobs():
    jobs = Job.objects.filter(status=Job.PENDING)
    # We're repurposing this celery setting to determine whether to run
    # pending jobs immediately. (It's similar to celery's semantics for
    # this setting.)
    if not settings.CELERY_ALWAYS_EAGER:
        jobs = jobs.filter(scheduled_start_date__lt=timezone.now())
    return jobs


@periodic_task(
    run_every=timedelta(minutes=3),
    ignore_result=True,
)
@full_job()
def run_scheduled_jobs():
    """
    Add scheduled jobs to the celery queue.

    This task itself gets job-tracking as well, to enforce that only one
    thread runs this task at a time. That way, no job looped through in this
    task can get started in celery multiple times.

    For reference:
    https://docs.celeryq.dev/en/v5.2.7/userguide/periodic-tasks.html
    "Like with cron, the tasks may overlap if the first task doesn’t complete
    before the next. If that’s a concern you should use a locking strategy
    to ensure only one instance can run at a time"
    """
    for job in get_scheduled_jobs():
        starter_task = job_starter_tasks[job.job_name]
        starter_task.delay(*Job.identifier_to_args(job.arg_identifier))


def run_scheduled_jobs_until_empty():
    """
    For testing purposes, it's convenient to schedule + run jobs, and
    then also run the jobs which have been scheduled by those jobs,
    using just one call.
    """
    while get_scheduled_jobs().exists():
        run_scheduled_jobs()


@periodic_task(
    run_every=timedelta(days=1),
    ignore_result=True)
def clean_up_old_jobs():
    current_time = timezone.now()
    x_days_ago = current_time - timedelta(days=settings.JOB_MAX_DAYS)

    # Clean up Jobs which are old enough since last modification,
    # and which are not tied to an ApiJobUnit.
    # The API-related Jobs should get cleaned up some time after
    # their ApiJobUnits get cleaned up.
    jobs_to_clean_up = Job.objects.filter(
        modify_date__lt=x_days_ago,
        apijobunit__isnull=True,
    )
    jobs_to_clean_up.delete()


@periodic_task(
    run_every=timedelta(days=1),
    ignore_result=True)
def report_stuck_jobs():
    """
    Report non-completed Jobs that haven't progressed since a certain
    number of days.
    """
    # When a non-completed Job hasn't been modified in this many days,
    # we'll consider it to be stuck.
    STUCK = 3

    # This task runs every day, and we don't issue repeat warnings for
    # the same jobs on subsequent days. So, only grab jobs whose last
    # progression was between STUCK days and STUCK+1 days ago.
    stuck_days_ago = timezone.now() - timedelta(days=STUCK)
    stuck_plus_one_days_ago = stuck_days_ago - timedelta(days=1)
    stuck_jobs_to_report = Job.objects \
        .filter(
            modify_date__lt=stuck_days_ago,
            modify_date__gt=stuck_plus_one_days_ago,
        ) \
        .exclude(status__in=[Job.SUCCESS, Job.FAILURE])

    if not stuck_jobs_to_report.exists():
        return

    stuck_job_count = stuck_jobs_to_report.count()
    subject = f"{stuck_job_count} job(s) haven't progressed in {STUCK} days"

    message = f"The following job(s) haven't progressed in {STUCK} days:\n"
    for job in stuck_jobs_to_report:
        message += f"\n{job}"

    mail_admins(subject, message)
