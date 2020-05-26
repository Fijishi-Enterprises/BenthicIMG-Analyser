"""
This file contains helper functions to vision_backend.tasks.
"""
import logging
from typing import List

import numpy as np
from django.conf import settings
from django.core.files.storage import get_storage_class
from django.db import transaction
from django.db.models import F
from django.utils import timezone
from reversion import revisions
from spacer.data_classes import ImageLabels
from spacer.messages import JobReturnMsg

from annotations.models import Annotation
from api_core.models import ApiJobUnit
from images.models import Image, Point
from .models import Classifier, Score

logger = logging.getLogger(__name__)


# Must explicitly turn on history creation when RevisionMiddleware is
# not in effect. (It's only in effect within views.)
@revisions.create_revision()
def _add_annotations(image_id, scores, label_objs, classifier):
    """
    Adds annotations objects using the classifier scores.

    :param image_id: Database ID of the Image to add scores for.
    :param scores: List of lists of score numbers. Same as in _add_scores().
    :param label_objs: Iterable of Label DB objects, one per label in the
      source's labelset.

    May throw an IntegrityError when trying to save annotations. The caller is
    responsible for handling the error. In this error case, no annotations
    are saved due to the transaction.atomic() context manager.

    NOTE: this function is SLOW.
    Note that bulk-saving annotations would skip the signal firing,
    and thus would not trigger django-reversion's revision creation.
    So we must save annotations one by one.
    """
    img = Image.objects.get(pk = image_id)
    points = Point.objects.filter(image=img).order_by('id')
    estlabels = [np.argmax(score) for score in scores]
    with transaction.atomic():
        for pt, estlabel in zip(points, estlabels):
            
            label = label_objs[int(estlabel)]

            Annotation.objects.update_point_annotation_if_applicable(
                point=pt, label=label,
                now_confirmed=False,
                user_or_robot_version=classifier)


def _add_scores(image_id, scores, label_objs):
    """
    Adds score objects using the classifier scores.

    :param image_id: Database ID of the Image to add scores for.
    :param scores: List of lists of score numbers.
      Each score number is a float; 0.65 to represent 65% probability. Will be
      rounded as needed.
      Each inner list consists of the scores for ALL labels in the source's
      labelset, for one particular point. The scores should be in the same
      order as label_objs.
      The outer list consists of one score list per point in the image. The
      points are assumed to be in database ID order.
    :param label_objs: Iterable of Label DB objects, one per label in the
      source's labelset.
    """
    img = Image.objects.get(pk = image_id)

    # First, delete all scores associated with this image.
    Score.objects.filter(image = img).delete()

    # Figure out how many of the (top) scores to store.
    nbr_scores = min(settings.NBR_SCORES_PER_ANNOTATION, len(scores[0]))

    # Now, go through and create new ones.
    points = Point.objects.filter(image = img).order_by('id')
    
    score_objs = []
    for point, score in zip(points, scores):
        inds = np.argsort(score)[::-1][:nbr_scores] # grab the index of the n highest index
        for ind in inds:
            score_objs.append(
                Score(
                    source = img.source, 
                    image = img, 
                    label = label_objs[int(ind)],
                    point = point, 
                    score = int(round(score[ind]*100))
                )
            )
    Score.objects.bulk_create(score_objs)


def make_dataset(images: List[Image]) -> ImageLabels:
    """
    Helper function for classifier_submit.
    Assembles all features and ground truth annotations
    for training and evaluation of the robot classifier.
    """
    storage = get_storage_class()()
    labels = ImageLabels(data={})
    for img in images:
        full_image_path = storage.path(img.original_file.name)
        feature_key = settings.FEATURE_VECTOR_FILE_PATTERN.format(
            full_image_path=full_image_path)
        anns = Annotation.objects.filter(image=img).\
            annotate(label=F('label__id')).\
            annotate(row=F('point__row')). \
            annotate(col=F('point__column'))
        labels.data[feature_key] = [(ann.row, ann.col, ann.label)
                                    for ann in anns]
    return labels


def _featurecollector(return_msg: JobReturnMsg):
    """
    collects feature_extract jobs.
    """
    # TODO: parse properly
    image_id = int(return_msg.original_job.tasks[0].job_token)
    try:
        img = Image.objects.get(pk=image_id)
    except Image.DoesNotExist:
        logger.info("Image {} not found. Aborting".format(image_id))
        return 0
    log_str = "Image {} [Source: {} [{}]]".format(image_id, img.source,
                                                  img.source_id)
        
    # Double-check that the row-col information is still correct.
    rowcols = [(p.row, p.column) for p in Point.objects.filter(image=img)]

    if not set(rowcols) == set(return_msg.original_job.tasks[0].rowcols):
        logger.info("Row-col for {} have changed. Aborting.".format(log_str))
        return 0
    
    # If all is ok store meta-data.
    img.features.extracted = True
    img.features.runtime_total = return_msg.results[0].runtime

    # TODO: remove this field from DB
    img.features.runtime_core = 0
    img.features.model_was_cashed = return_msg.results[0].model_was_cashed
    img.features.extracted_date = timezone.now()
    img.features.save()
    return 1


def _classifiercollector(messagebody):
    """
    collects train_classifier jobs.
    """
    result = messagebody['result']
    payload = messagebody['original_job']['payload']
    
    # Check that Classifier still exists. 
    try:
        classifier = Classifier.objects.get(pk = payload['pk'])
    except:
        logger.info("Classifier {} was deleted. Aborting".format(payload['pk']))
        return 0
    logstr = 'Classifier {} [Source: {} [{}]]'.format(classifier.pk, classifier.source, classifier.source.id)
    
    # If training didn't finish with OK status, return false and exit.
    if not result['ok']:
        return 0

    # Store generic stats
    classifier.runtime_train = result['runtime']
    classifier.accuracy = result['acc']
    classifier.epoch_ref_accuracy = str([int(round(10000 * ra)) for ra in result['refacc']])
    classifier.save()

    # Check that the accuracy is higher than the previous classifiers
    if 'pc_models' in payload and len(payload['pc_models']) > 0:
        if max(result['pc_accs']) * settings.NEW_CLASSIFIER_IMPROVEMENT_TH > result['acc']:
            logger.info("{} worse than previous. Not validated. Max previous: {:.2f}, threshold: {:.2f}, this: {:.2f}".format(logstr, max(result['pc_accs']), max(result['pc_accs']) * settings.NEW_CLASSIFIER_IMPROVEMENT_TH, result['acc']))
            return 0
        
        # Update accuracy for previous models
        for pc_pk, pc_acc in zip(payload['pc_pks'], result['pc_accs']):
            pc = Classifier.objects.get(pk=pc_pk)
            pc.accuracy = pc_acc
            pc.save()
    
    classifier.valid = True
    classifier.save()
    logger.info("{} collected successfully.".format(logstr))
    return 1


def _deploycollector(messagebody):

    def build_points_dicts(scores, classes, rowcols, labelset):
        """
        Converts scores from the deploy call to the dictionary returned
        by the API
        """

        # Figure out how many of the (top) scores to store.
        nbr_scores = min(settings.NBR_SCORES_PER_ANNOTATION, len(scores[0]))

        # Pre-fetch label objects. The local labels let us reach all the
        # fields we want.
        local_labels = []
        for class_ in classes:
            local_label = labelset.locallabel_set.get(global_label__pk=class_)
            local_labels.append(local_label)

        data = []
        for score, rowcol in zip(scores, rowcols):
            # grab the index of the highest indices
            inds = np.argsort(score)[::-1][:nbr_scores]
            classifications = []
            for ind in inds:
                local_label = local_labels[ind]
                classifications.append(dict(
                    label_id=local_label.global_label.pk,
                    label_name=local_label.global_label.name,
                    label_code=local_label.code,
                    score=score[ind]))
            data.append(dict(
                row=rowcol[0],
                column=rowcol[1],
                classifications=classifications
            ))
        return data

    result = messagebody['result']
    org_payload = messagebody['original_job']['payload']

    pk = org_payload['pk']
    try:
        job_unit = ApiJobUnit.objects.get(pk=pk)
    except ApiJobUnit.DoesNotExist:
        logger.info("Job unit of id {} does not exist.".format(pk))
        return

    try:
        classifier = Classifier.objects.get(
            pk=job_unit.request_json['classifier_id'])
    except Classifier.DoesNotExist:
        logger.info("Classifier of id {} does not exist.".format(pk))
        return

    if result['ok']:
        job_unit.result_json = dict(
            url=job_unit.request_json['url'],
            points=build_points_dicts(
                result['scores'],
                result['classes'],
                org_payload['rowcols'],
                classifier.source.labelset)
        )
        job_unit.status = ApiJobUnit.SUCCESS
    else:
        job_unit.result_json = dict(
            url=job_unit.request_json['url'],
            error=result['error']
        )
        job_unit.status = ApiJobUnit.FAILURE
    job_unit.save()
