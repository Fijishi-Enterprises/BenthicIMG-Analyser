import logging
from datetime import timedelta

from celery.decorators import task, periodic_task

from images.models import Point, Image
from annotations.models import Annotation
from annotations.utils import (
    purge_annotations, update_sitewide_annotation_count)

logger = logging.getLogger(__name__)


@periodic_task(run_every=timedelta(days=7), name='Periodic Annotation Purge', ignore_result=True)
def clean_annotations():
    """
    Crawl DB to find points with multiple annotations. (Such points'
    'should not exist, but due to a race condition problem, they do)'

    NOTE: this will only clean image for which the total number of annotations is larger than
    the total number of points. In yet-to-be-seen cases, it could happen that while some points
    have more than one annotation, the total number of annotations is smaller than the number
    of points.
    """

    for image in Image.objects.filter():
        nbr_points = Point.objects.filter(image=image.pk).count()
        nbr_anns = Annotation.objects.filter(image=image.pk).count()
        if nbr_anns > nbr_points:
            purge_annotations(image.id)
            logger.info("Purged annotations for image {}.".format(image_id))


@periodic_task(run_every=timedelta(days=1), name='Update Sitewide Annotation Count', ignore_result=True)
def update_sitewide_annotation_count_task():
    update_sitewide_annotation_count()
