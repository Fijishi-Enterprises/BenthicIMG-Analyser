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

from spacer.messages import \
    ExtractFeaturesMsg, \
    ExtractFeaturesReturnMsg, \
    TrainClassifierMsg, \
    TrainClassifierReturnMsg, \
    ClassifyFeaturesMsg, \
    ClassifyImageMsg, \
    ClassifyReturnMsg, \
    JobMsg, \
    JobReturnMsg, \
    DataLocation

from annotations.models import Annotation
from api_core.models import ApiJobUnit
from images.models import Image, Point
from .models import Classifier, Score
from labels.model import Label

from lib.storage_backends import MediaStorageLocal, MediaStorageS3

logger = logging.getLogger(__name__)


def storage_class_to_str(storage) -> str:

    if isinstance(storage, MediaStorageLocal):
        return 'filesystem'
    if isinstance(storage, MediaStorageS3):
        return 's3'

    raise ValueError('Unknown storage type {}'.format(type(storage)))


# Must explicitly turn on history creation when RevisionMiddleware is
# not in effect. (It's only in effect within views.)
@revisions.create_revision()
def add_annotations(image_id: int,
                    res: ClassifyReturnMsg,
                    label_objs: List[Label],
                    classifier: Classifier):
    """
    Adds annotations objects using the classifier scores.

    :param image_id: Database ID of the Image to add scores for.
    :param res: ClassifyReturnMessage from spacer.
    :param label_objs: Iterable of Label DB objects, one per label in the
      source's labelset.
    :param classifier: Classifier object.

    May throw an IntegrityError when trying to save annotations. The caller is
    responsible for handling the error. In this error case, no annotations
    are saved due to the transaction.atomic() context manager.

    NOTE: this function is SLOW.
    Note that bulk-saving annotations would skip the signal firing,
    and thus would not trigger django-reversion's revision creation.
    So we must save annotations one by one.
    """
    img = Image.objects.get(pk=image_id)
    points = Point.objects.filter(image=img).order_by('id')

    with transaction.atomic():
        def _store_ann(label_obj, point_):
            """ Helper method """
            Annotation.objects.update_point_annotation_if_applicable(
                point=point_,
                label=label_obj,
                now_confirmed=False,
                user_or_robot_version=classifier)

        if res.valid_rowcol:
            # From spacer 0.2 we store row, col locations in features and in
            # classifier scores. This allows us to match scores to points
            # based on (row, col) locations. If not, we have to rely on
            # the points always being ordered as order_by('id').
            for point in points:
                # Retrieve score vector for (row, column) location
                scores = res[(point.row, point.column)]
                _store_ann(label_objs[int(np.argmax(scores))], point)
        else:
            for point, (_, _, scores) in zip(points, res.scores):
                _store_ann(label_objs[int(np.argmax(scores))], point)


def add_scores(image_id: int,
               res: ClassifyReturnMsg,
               label_objs: List[Label]):
    """
    Adds score objects using the classifier scores.

    :param image_id: Database ID of the Image to add scores for.
    :param res: ClassifyReturnMessage from spacer.
    :param label_objs: Iterable of Label DB objects, one per label in the
      source's labelset.
    """
    img = Image.objects.get(pk=image_id)

    # First, delete all scores associated with this image.
    Score.objects.filter(image=img).delete()

    # Figure out how many of the (top) scores to store.
    nbr_scores = min(settings.NBR_SCORES_PER_ANNOTATION, len(res.classes))

    # Now, go through and create new ones.
    points = Point.objects.filter(image=img).order_by('id')
    
    score_objs = []
    for point, score in zip(points, scores):
        # grab the index of the n highest index
        inds = np.argsort(score)[::-1][:nbr_scores]
        for ind in inds:
            score_objs.append(
                Score(
                    source=img.source,
                    image=img,
                    label=label_objs[int(ind)],
                    point=point,
                    score=int(round(score[ind]*100))
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
            annotate(gt_label=F('label__id')).\
            annotate(row=F('point__row')). \
            annotate(col=F('point__column'))
        labels.data[feature_key] = [(ann.row, ann.col, ann.gt_label)
                                    for ann in anns]
    return labels


def featurecollector(task: ExtractFeaturesMsg, res: ExtractFeaturesReturnMsg):
    """
    collects feature_extract jobs.
    """
    image_id = int(task.job_token)
    try:
        img = Image.objects.get(pk=image_id)
    except Image.DoesNotExist:
        logger.info("Image {} not found. Aborting".format(image_id))
        return 0
    log_str = "Image {} [Source: {} [{}]]".format(image_id, img.source,
                                                  img.source_id)
        
    # Double-check that the row-col information is still correct.
    rowcols = [(p.row, p.column) for p in Point.objects.filter(image=img)]

    if not set(rowcols) == set(task.rowcols):
        logger.info("Row-col for {} have changed. Aborting.".format(log_str))
        return 0
    
    # If all is ok store meta-data.
    img.features.extracted = True
    img.features.runtime_total = res.runtime

    # TODO: remove runtime_core from DB
    img.features.runtime_core = 0
    img.features.model_was_cashed = res.model_was_cashed
    img.features.extracted_date = timezone.now()
    img.features.save()
    return True


def classifiercollector(task: TrainClassifierMsg,
                        res: TrainClassifierReturnMsg):
    """
    collects train_classifier jobs.
    """
    # Parse out pk for current and previous classifiers.
    pks = [int(entry) for entry in task.job_token.split(',')]
    pk = pks[0]
    prev_pks = pks[1:]

    assert len(prev_pks) == len(res.pc_accs), \
        "Number of previous classifiers doesn't match between job ({}) and " \
        "results ({}).".format(len(prev_pks), len(res.pc_accs))

    # Check that Classifier still exists. 
    try:
        classifier = Classifier.objects.get(pk=pk)
    except Classifier.DoesNotExist:
        logger.info("Classifier {} was deleted. Aborting".
                    format(task.job_token))
        return False
    log_str = 'Classifier {} [Source: {} [{}]]'.format(classifier.pk,
                                                       classifier.source,
                                                       classifier.source.id)

    # Store generic stats
    classifier.runtime_train = res.runtime
    classifier.accuracy = res.acc
    classifier.epoch_ref_accuracy = str([int(round(10000 * ra)) for
                                         ra in res.ref_accs])
    classifier.save()

    # If there are previous classifiers and the new one is not a large enough
    # improvement, abort without validating the new classifier.
    if len(prev_pks) > 0 and max(res.pc_accs) * \
            settings.NEW_CLASSIFIER_IMPROVEMENT_TH > res.acc:
        logger.info(
            "{} worse than previous. Not validated. Max previous: {:.2f}, "
            "threshold: {:.2f}, this: {:.2f}".format(
                log_str,
                max(res.pc_accs),
                max(res.pc_accs) * settings.NEW_CLASSIFIER_IMPROVEMENT_TH,
                res.acc))
        return False

    # Update accuracy for previous models.
    for pc_pk, pc_acc in zip(prev_pks, res.pc_accs):
        pc = Classifier.objects.get(pk=pc_pk)
        pc.accuracy = pc_acc
        pc.save()

    # Validate and save the current model
    classifier.valid = True
    classifier.save()
    logger.info("{} collected successfully.".format(log_str))
    return True


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
