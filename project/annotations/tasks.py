from datetime import timedelta

from jobs.utils import job_runner
from .utils import update_sitewide_annotation_count


@job_runner(
    interval=timedelta(days=1),
    job_name='update_sitewide_annotation_count',
)
def update_sitewide_annotation_count_task():
    count = update_sitewide_annotation_count()
    return f"Updated count to {count}"
