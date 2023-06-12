from datetime import timedelta

from jobs.utils import job_runner
from .models import Label


@job_runner(interval=timedelta(days=7))
def update_label_popularities():
    for label in Label.objects.all():
        label._compute_popularity()
