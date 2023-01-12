from django.core.management.base import BaseCommand

from jobs.models import Job
from jobs.utils import finish_job


class Command(BaseCommand):
    help = (
        "Abort Job instances by ID. Useful if a Job is known to be stuck."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            'job_ids', type=int, nargs='+',
            help="List of Job IDs to abort")

    def handle(self, *args, **options):
        job_ids = options.get('job_ids')
        for job_id in job_ids:
            job = Job.objects.get(pk=job_id)
            finish_job(job, success=False, result_message="Aborted manually")
        self.stdout.write(
            f"The {len(job_ids)} specified Job(s) have been aborted.")
