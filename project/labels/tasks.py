from datetime import timedelta

from jobs.utils import job_runner
from .models import Label


@job_runner(interval=timedelta(days=7))
def update_label_popularities():
    labels = Label.objects.all()
    for label in labels:
        label._compute_popularity()
    return f"Updated popularities for all {labels.count()} label(s)"
