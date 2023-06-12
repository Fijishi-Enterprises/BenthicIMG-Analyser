from datetime import timedelta

from jobs.utils import job_runner
from .utils import update_sitewide_annotation_count


@job_runner(interval=timedelta(days=1))
def update_sitewide_annotation_count_task():
    update_sitewide_annotation_count()
