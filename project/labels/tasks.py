from huey import crontab

from jobs.utils import full_job
from .models import Label


@full_job(schedule=crontab(day_of_week=0, hour=0, minute=0))
def update_label_popularities():
    for label in Label.objects.all():
        label._compute_popularity()
