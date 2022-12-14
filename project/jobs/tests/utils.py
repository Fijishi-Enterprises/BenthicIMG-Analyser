from ..models import Job
from ..utils import queue_job


def queue_job_with_modify_date(*args, modify_date=None, **kwargs):
    job = queue_job(*args, **kwargs)

    # Use QuerySet.update() instead of Model.save() so that the modify
    # date doesn't get auto-updated to the current date.
    Job.objects.filter(pk=job.pk).update(modify_date=modify_date)

    return job
