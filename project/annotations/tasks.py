from datetime import timedelta

from celery.decorators import task, periodic_task

from .utils import update_sitewide_annotation_count


@periodic_task(run_every=timedelta(days=1), name='Update Sitewide Annotation Count', ignore_result=True)
def update_sitewide_annotation_count_task():
    update_sitewide_annotation_count()
