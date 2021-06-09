from datetime import timedelta

from celery.decorators import periodic_task

from .models import Label


@periodic_task(
    run_every=timedelta(days=7), name='Update Label Popularities',
    ignore_result=True)
def update_label_popularities():
    for label in Label.objects.all():
        label._compute_popularity()
