"""
This file contains helper functions to vision_backend.tasks.
"""
from abc import ABC
from datetime import timedelta
import logging
from typing import List

import numpy as np
from django.conf import settings
from django.core.files.storage import get_storage_class
from django.core.mail import mail_admins
from django.db import transaction
from django.db.models import F
from django.utils.timezone import now
from reversion import revisions
from spacer.data_classes import ImageLabels
from spacer.messages import \
    ExtractFeaturesMsg, \
    ExtractFeaturesReturnMsg, \
    TrainClassifierMsg, \
    TrainClassifierReturnMsg, \
    ClassifyImageMsg, \
    ClassifyReturnMsg, \
    JobReturnMsg

from annotations.models import Annotation
from api_core.models import ApiJobUnit
from images.models import Image, Point
from labels.models import Label, LabelSet
from .models import Classifier, Score

logger = logging.getLogger(__name__)


def encode_spacer_job_token(pks: List[int]):
    """ Encodes a list of primary keys into a spacer job_token string """
    return '_'.join([str(pk) for pk in pks])


def decode_spacer_job_token(job_token: str):
    """ Decodes spacer job token """
    pks = [int(pk) for pk in job_token.split('_')]
    return pks


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

    # From spacer 0.2 we store row, col locations in features and in
    # classifier scores. This allows us to match scores to points
    # based on (row, col) locations. If not, we have to rely on
    # the points always being ordered as order_by('id').
    for itt, point in enumerate(points):
        if res.valid_rowcol:
            # Retrieve score vector for (row, column) location
            scores = res[(point.row, point.column)]
        else:
            _, _, scores = res.scores[itt]
        with transaction.atomic():
            Annotation.objects.update_point_annotation_if_applicable(
                point=point,
                label=label_objs[int(np.argmax(scores))],
                now_confirmed=False,
                user_or_robot_version=classifier)


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
    for itt, point in enumerate(points):
        if res.valid_rowcol:
            scores = res[(point.row, point.column)]
        else:
            _, _, scores = res.scores[itt]
        inds = np.argsort(scores)[::-1][:nbr_scores]
        for ind in inds:
            score_objs.append(
                Score(
                    source=img.source,
                    image=img,
                    label=label_objs[int(ind)],
                    point=point,
                    score=int(round(scores[ind]*100))
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
        data_loc = storage.spacer_data_loc(img.original_file.name)
        feature_key = settings.FEATURE_VECTOR_FILE_PATTERN.format(
            full_image_path=data_loc.key)
        anns = Annotation.objects.filter(image=img).\
            annotate(gt_label=F('label__id')).\
            annotate(row=F('point__row')). \
            annotate(col=F('point__column'))
        labels.data[feature_key] = [(ann.row, ann.col, ann.gt_label)
                                    for ann in anns]
    return labels


class JobResultHandler(ABC):
    """
    Each type of collectable vision-backend job should define a subclass
    of this base class.
    """
    task_name = None

    @classmethod
    def handle(cls, job_res: JobReturnMsg):
        if not job_res.ok:
            logger.error(f"Job failed: {job_res.error_message}")
            cls.handle_job_error(job_res)
            return

        for task, task_res in zip(job_res.original_job.tasks, job_res.results):
            pk = decode_spacer_job_token(task.job_token)[0]
            cls.handle_task_result(task, task_res)
            logger.info(f"Collected job: {cls.task_name} with pk: {pk}")

    @staticmethod
    def handle_job_error(job_res: JobReturnMsg):
        mail_admins("Spacer job failed", repr(job_res))

    @staticmethod
    def handle_task_result(task, task_res):
        raise NotImplementedError


class FeatureJobResultHandler(JobResultHandler):
    task_name = 'extract_features'

    @staticmethod
    def handle_task_result(
            task: ExtractFeaturesMsg, res: ExtractFeaturesReturnMsg):
        image_id = decode_spacer_job_token(task.job_token)[0]
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
            logger.info(f"Row-col for {log_str} have changed. Aborting.")
            return 0

        # If all is ok store meta-data.
        img.features.extracted = True
        img.features.runtime_total = res.runtime

        # TODO: remove runtime_core from DB
        img.features.runtime_core = 0
        img.features.model_was_cashed = res.model_was_cashed
        img.features.extracted_date = now()
        img.features.save()

        # Submit a classify job.
        from .tasks import classify_image
        classify_image.apply_async(args=[image_id],
                                   eta=now() + timedelta(seconds=10))


class TrainJobResultHandler(JobResultHandler):
    task_name = 'train_classifier'

    @staticmethod
    def handle_job_error(job_res: JobReturnMsg):
        job_token = job_res.original_job.tasks[0].job_token
        pk = decode_spacer_job_token(job_token)[0]

        try:
            classifier = Classifier.objects.get(pk=pk)
        except Classifier.DoesNotExist:
            # This should be an edge case, where the user reset the classifiers
            # or deleted the source before training could complete.
            logger.info(
                "Training failed for classifier {}, although the classifier"
                " was already deleted.".format(job_token))
            return

        classifier.status = Classifier.TRAIN_ERROR
        classifier.save()
        logger.info(
            "Training failed for classifier {}.".format(job_token))

        # Sometimes training fails because features were temporarily de-synced
        # with the points. We'll take different actions depending on the number
        # of train attempts that failed in a row.
        source = classifier.source
        last_classifiers = source.classifier_set.order_by('-pk')[:5]
        train_fails_in_a_row = 0
        for clf in last_classifiers:
            if clf.status == Classifier.TRAIN_ERROR:
                train_fails_in_a_row += 1
            else:
                break

        from .tasks import reset_features, submit_classifier

        if train_fails_in_a_row <= 1:
            # Only 1 fail so far.
            # Sometimes the features are getting re-extracted, and just didn't
            # finish yet. We'll hope for that here.
            submit_classifier.apply_async(
                args=[source.pk],
                eta=now() + timedelta(hours=3))
        elif 2 <= train_fails_in_a_row <= 3:
            # Go through all the source's images and force-extract features.
            for image in source.image_set.all():
                reset_features.apply_async(
                    args=[image.pk],
                    eta=now() + timedelta(seconds=10))
            # Hopefully this eta is enough time for the features to get
            # extracted, regardless of image count.
            # (The "2 or 3" check attempts to cover for the case where train
            # number 3 happens very soon from submit_all_classifiers(), thus
            # leaving no time for feature extraction.)
            submit_classifier.apply_async(
                args=[source.pk],
                eta=now() + timedelta(hours=8))
        else:
            # 4 or more fails in a row. Notify the admins.
            mail_admins("Spacer job failed", repr(job_res))
            # Next retrain happens when submit_all_classifiers() is run
            # (<= 24 hours).

    @staticmethod
    def handle_task_result(
            task: TrainClassifierMsg, res: TrainClassifierReturnMsg):
        # Parse out pk for current and previous classifiers.
        pks = decode_spacer_job_token(task.job_token)
        pk = pks[0]
        prev_pks = pks[1:]

        assert len(prev_pks) == len(res.pc_accs), \
            f"Number of previous classifiers doesn't match between" \
            f" job ({len(prev_pks)}) and results ({len(res.pc_accs)})."

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

        # If there are previous classifiers and the new one is not a large
        # enough improvement, abort without validating the new classifier.
        if len(prev_pks) > 0 and max(res.pc_accs) * \
                settings.NEW_CLASSIFIER_IMPROVEMENT_TH > res.acc:

            classifier.status = Classifier.REJECTED_ACCURACY
            classifier.save()
            logger.info(
                "{} worse than previous. Not accepted. Max previous: {:.2f}, "
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

        # Accept and save the current model
        classifier.status = Classifier.ACCEPTED
        classifier.save()
        logger.info("{} collected successfully.".format(log_str))

        # If successful, submit a classify job for all imgs in source.
        from .tasks import classify_image
        classifier = Classifier.objects.get(pk=pk)
        for image in Image.objects.filter(source=classifier.source,
                                          features__extracted=True,
                                          annoinfo__confirmed=False):
            classify_image.apply_async(
                args=[image.id],
                eta=now() + timedelta(seconds=10))


class ClassifyJobResultHandler(JobResultHandler):
    task_name = 'classify_image'

    @staticmethod
    def handle_job_error(job_res: JobReturnMsg):
        mail_admins("Spacer job failed", repr(job_res))

        pk = decode_spacer_job_token(
            job_res.original_job.tasks[0].job_token)[0]
        try:
            job_unit = ApiJobUnit.objects.get(pk=pk)
        except ApiJobUnit.DoesNotExist:
            logger.info("Job unit of id {} does not exist.".format(pk))
            return

        job_unit.result_json = dict(
            url=job_unit.request_json['url'],
            errors=[job_res.error_message],
        )
        job_unit.status = ApiJobUnit.FAILURE
        job_unit.save()

    @classmethod
    def handle_task_result(
            cls, task: ClassifyImageMsg, res: ClassifyReturnMsg):

        pk = decode_spacer_job_token(task.job_token)[0]
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

        job_unit.result_json = dict(
            url=job_unit.request_json['url'],
            points=cls.build_points_dicts(res, classifier.source.labelset)
        )
        job_unit.status = ApiJobUnit.SUCCESS
        job_unit.save()

    @staticmethod
    def build_points_dicts(res: ClassifyReturnMsg, labelset: LabelSet):
        """
        Converts scores from the deploy call to the dictionary returned
        by the API
        """

        # Figure out how many of the (top) scores to store.
        nbr_scores = min(settings.NBR_SCORES_PER_ANNOTATION,
                         len(res.classes))

        # Pre-fetch label objects. The local labels let us reach all the
        # fields we want.
        local_labels = []
        for class_ in res.classes:
            local_label = labelset.locallabel_set.get(global_label__pk=class_)
            local_labels.append(local_label)

        data = []
        for row, col, scores in res.scores:
            # grab the index of the highest indices
            inds = np.argsort(scores)[::-1][:nbr_scores]
            classifications = []
            for ind in inds:
                local_label = local_labels[ind]
                classifications.append(dict(
                    label_id=local_label.global_label.pk,
                    label_name=local_label.global_label.name,
                    label_code=local_label.code,
                    score=scores[ind]))
            data.append(dict(row=row,
                             column=col,
                             classifications=classifications
                             )
                        )
        return data


handler_classes = [
    FeatureJobResultHandler,
    TrainJobResultHandler,
    ClassifyJobResultHandler,
]


def handle_job_result(job_res: JobReturnMsg):
    """Handles the job results found in queue. """

    task_name = job_res.original_job.task_name
    for HandlerClass in handler_classes:
        if task_name == HandlerClass.task_name:
            HandlerClass.handle(job_res)
            return
    logger.error(f"Job task type {task_name} not recognized")
