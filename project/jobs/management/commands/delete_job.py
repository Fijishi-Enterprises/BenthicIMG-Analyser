from django.core.management.base import BaseCommand

from jobs.models import Job


class Command(BaseCommand):
    help = (
        "Delete Job instances by ID. Useful if a Job is known to be stuck."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            'job_ids', type=int, nargs='+',
            help="List of Job IDs to delete")

    def handle(self, *args, **options):
        job_ids = options.get('job_ids')
        for job_id in job_ids:
            job = Job.objects.get(pk=job_id)
            job.delete()
        self.stdout.write(
            f"The {len(job_ids)} specified Job(s) have been deleted.")
