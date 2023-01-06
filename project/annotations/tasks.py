from huey import crontab

from jobs.utils import full_job
from .utils import update_sitewide_annotation_count


@full_job(schedule=crontab(hour=0, minute=0))
def update_sitewide_annotation_count_task():
    update_sitewide_annotation_count()
