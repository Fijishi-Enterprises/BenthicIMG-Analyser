from collections import Counter
import datetime
from datetime import timedelta
import logging
import random

from django.conf import settings
from django.core.files.storage import get_storage_class
from django.db import IntegrityError
from django.db.models import F
from django.utils import timezone
from spacer.messages import \
    ExtractFeaturesMsg, \
    TrainClassifierMsg, \
    ClassifyFeaturesMsg, \
    ClassifyImageMsg, \
    ClassifyReturnMsg, \
    JobMsg, \
    DataLocation
from spacer.tasks import classify_features as spacer_classify_features

from annotations.models import Annotation
from api_core.models import ApiJobUnit
from images.models import Source, Image, Point
from jobs.exceptions import JobError
from jobs.models import Job
from jobs.utils import job_runner, job_starter, queue_job
from labels.models import Label
from . import task_helpers as th
from .models import Classifier, Score
from .queues import get_queue_class
from .utils import queue_source_check, reset_features

logger = logging.getLogger(__name__)


# Run daily, and not at prime times of biggest users (e.g. US East, Hawaii,
# Australia).
@job_runner(
    interval=timedelta(days=1),
    offset=datetime.datetime(
        year=2023, month=1, day=1, hour=7, minute=0,
        tzinfo=datetime.timezone.utc,
    ),
)
def check_all_sources():
    queued = 0
    for source in Source.objects.all():
        # Queue a check of this source at a random time in the next 4 hours.
        delay_in_seconds = random.randrange(1, 60*60*4)
        job = queue_source_check(
            source.pk, delay=timedelta(seconds=delay_in_seconds))
        if job:
            queued += 1
    return f"Queued checks for {queued} source(s)"


@job_runner()
def check_source(source_id):
    """
    Check a source for appropriate vision-backend tasks to run,
    and run those tasks.
    """
    try:
        source = Source.objects.get(pk=source_id)
    except Source.DoesNotExist:
        raise JobError(f"Can't find source {source_id}")

    start = timezone.now()
    wrap_up_time = start + timedelta(minutes=settings.JOB_MAX_MINUTES)
    timed_out = False

    done_caveat = None

    # Feature extraction

    not_extracted = source.image_set.filter(features__extracted=False)
    not_extracted = not_extracted.annotate(
        num_pixels=F('original_width') * F('original_height'))
    cant_extract = not_extracted.filter(
        num_pixels__gt=settings.SPACER['MAX_IMAGE_PIXELS'])
    to_extract = not_extracted.difference(cant_extract)

    if to_extract.exists():
        active_training_jobs = Job.objects.filter(
            job_name='train_classifier',
            source_id=source_id,
            status__in=[Job.Status.PENDING, Job.Status.IN_PROGRESS]
        )
        if active_training_jobs.exists():
            # If we submit, rowcols that were submitted to training may get
            # out of sync with features in S3.
            # The potentially dangerous sequence is like:
            #
            # 1) submit training to spacer with old point set
            # 2) upload new point set for training images
            # 3) as a result of the upload, submit associated feature
            # extractions to spacer
            # 4) spacer runs feature extractions, replacing old feature
            # files with new feature files
            # 5) spacer runs training with old point set + new feature files.
            #
            # So, we prevent 3) from being able to happen.
            return (
                f"Feature extraction(s) ready, but not"
                f" submitted due to training in progress")

        active_extraction_jobs = Job.objects.filter(
            job_name='extract_features',
            source_id=source_id,
            status__in=[Job.Status.PENDING, Job.Status.IN_PROGRESS]
        )
        active_extraction_image_ids = set([
            int(str_id) for str_id in
            active_extraction_jobs.values_list('arg_identifier', flat=True)
        ])

        # Try to queue extractions (will not be queued if an extraction for
        # the same image is already active)
        num_queued_extractions = 0
        for image in to_extract:
            if image.pk in active_extraction_image_ids:
                # Very quick short-circuit without additional DB check.
                continue

            # This hits the DB to check for a race condition (identical
            # active job), then to create a job as appropriate.
            job = queue_job('extract_features', image.pk, source_id=source_id)
            if not job:
                continue

            num_queued_extractions += 1

            if (
                num_queued_extractions % 10 == 0
                and timezone.now() > wrap_up_time
            ):
                timed_out = True
                break

        # If there are extractions to be done, then having that overlap with
        # training can lead to desynced rowcols, so we return and worry about
        # training later.
        if num_queued_extractions > 0:
            result_str = (
                f"Queued {num_queued_extractions} feature extraction(s)")
            if timed_out:
                result_str += " (timed out)"
            return result_str
        else:
            return "Waiting for feature extraction(s) to finish"

    if cant_extract.exists():
        done_caveat = (
            f"At least one image has too large of a resolution to extract"
            f" features (example: image ID {cant_extract[0].pk}).")

    # Classifier training

    need_new_robot, reason = source.need_new_robot()
    if need_new_robot:
        # Try to queue training
        job = queue_job('train_classifier', source_id, source_id=source_id)
        # We return and don't worry about classification until the classifier
        # is up to date.
        if job:
            return "Queued training"
        else:
            return "Waiting for training to finish"

    # Image classification

    if not source.has_robot():
        return f"Can't train first classifier: {reason}"
    extracted_not_confirmed = source.image_set.filter(
        features__extracted=True,
        annoinfo__confirmed=False,
    )
    extracted_not_classified = extracted_not_confirmed.filter(
        features__classified=False,
    )
    latest_classifier_annotations = source.annotation_set \
        .filter(robot_version=source.get_current_classifier())

    if latest_classifier_annotations.exists():
        # The classifier version of an annotation only gets updated if the
        # new classifier disagrees with the old classifier. So we can't
        # tell what's outdated by only looking at a single annotation's
        # classifier version.
        # But in general, we are never in a state where some classifications
        # have been last checked by the latest classifier, and others have
        # been last checked by an old classifier. It's either all latest,
        # or all old.
        # So if the latest classifier has ANY annotations attributed to it,
        # we only worry about unclassified images.
        images_to_classify = extracted_not_classified
    else:
        # If there's no trace of the latest classifier, then we go through
        # all non-confirmed images.
        images_to_classify = extracted_not_confirmed

    if images_to_classify.exists():

        active_classify_jobs = Job.objects.filter(
            job_name='classify_features',
            source_id=source_id,
            status__in=[Job.Status.PENDING, Job.Status.IN_PROGRESS]
        )
        active_classify_image_ids = set([
            int(str_id) for str_id in
            active_classify_jobs.values_list('arg_identifier', flat=True)
        ])

        # Try to queue classifications
        num_queued_classifications = 0
        for image in images_to_classify:
            if image.pk in active_classify_image_ids:
                # Very quick short-circuit without additional DB check.
                continue

            job = queue_job('classify_features', image.pk, source_id=source_id)
            if not job:
                continue

            num_queued_classifications += 1

            if (
                num_queued_classifications % 10 == 0
                and timezone.now() > wrap_up_time
            ):
                timed_out = True
                break

        if num_queued_classifications > 0:
            result_str = (
                f"Queued {num_queued_classifications} image classification(s)")
            if timed_out:
                result_str += " (timed out)"
            return result_str
        else:
            return "Waiting for image classification(s) to finish"

    # If we got here, then the source should be all caught up, and there's
    # no need to queue another check for now. However, there may be a caveat
    # to the 'caught up' status.
    if done_caveat:
        return (
            f"{done_caveat} Otherwise, the source seems to be all caught up."
            f" {reason}")
    return f"Source seems to be all caught up. {reason}"


@job_starter(job_name='extract_features')
def submit_features(image_id, job_id):
    """ Submits a feature extraction job. """
    try:
        img = Image.objects.get(pk=image_id)
    except Image.DoesNotExist:
        raise JobError(f"Image {image_id} does not exist.")

    # Setup the job payload.
    storage = get_storage_class()()

    # Assemble row column information
    rowcols = [(p.row, p.column) for p in Point.objects.filter(image=img)]

    # Assemble task.
    task = ExtractFeaturesMsg(
        job_token=str(job_id),
        feature_extractor_name=img.source.feature_extractor,
        rowcols=rowcols,
        image_loc=storage.spacer_data_loc(img.original_file.name),
        feature_loc=storage.spacer_data_loc(
            settings.FEATURE_VECTOR_FILE_PATTERN.format(
                full_image_path=img.original_file.name))
    )

    msg = JobMsg(task_name='extract_features', tasks=[task])

    # Submit.
    queue = get_queue_class()()
    queue.submit_job(msg, job_id)

    logger.info(f"Submitted feature extraction for {img}")
    return msg


@job_starter(job_name='train_classifier')
def submit_classifier(source_id, job_id):
    """ Submits a classifier training job. """

    # We know the Source exists since we got past the job_starter decorator,
    # and deleting the Source would've cascade-deleted the Job.
    source = Source.objects.get(pk=source_id)

    # Create new classifier model
    IMAGE_LIMIT = 1e5
    images = Image.objects.filter(source=source,
                                  annoinfo__confirmed=True,
                                  features__extracted=True)[:IMAGE_LIMIT]
    classifier = Classifier(
        source=source, train_job_id=job_id, nbr_train_images=len(images))
    classifier.save()

    logger.info(f"Preparing: {classifier}")

    # Create train-labels
    storage = get_storage_class()()
    train_labels = th.make_dataset(
        [image for image in images if image.trainset])

    # Create val-labels
    val_labels = th.make_dataset([image for image in images if image.valset])

    # Identify classes common to both train and val. This will be our labelset
    # for the training.
    # Here we check that there are at least 2 unique labels for training. If
    # not, we can get stuck in an error loop if we proceed to submit training
    # (see issue #412), so we don't submit training.
    train_data_classes = train_labels.unique_classes(train_labels.image_keys)
    val_data_classes = val_labels.unique_classes(val_labels.image_keys)
    training_classes = train_data_classes.intersection(val_data_classes)
    if len(training_classes) <= 1:
        classifier.status = Classifier.LACKING_UNIQUE_LABELS
        classifier.save()
        raise JobError(
            f"{classifier} was declined training, because the training"
            f" labelset ended up only having one unique label. Training"
            f" requires at least 2 unique labels.")

    # This will not include the one we just created, b/c status isn't accepted.
    prev_classifiers = source.get_accepted_robots()

    # Create TrainClassifierMsg
    task = TrainClassifierMsg(
        job_token=str(job_id),
        trainer_name='minibatch',
        nbr_epochs=settings.NBR_TRAINING_EPOCHS,
        clf_type=settings.CLASSIFIER_MAPPINGS[source.feature_extractor],
        train_labels=train_labels,
        val_labels=val_labels,
        features_loc=storage.spacer_data_loc(''),
        previous_model_locs=[storage.spacer_data_loc(
            settings.ROBOT_MODEL_FILE_PATTERN.format(pk=pc.pk))
            for pc in prev_classifiers],
        model_loc=storage.spacer_data_loc(
            settings.ROBOT_MODEL_FILE_PATTERN.format(pk=classifier.pk)),
        valresult_loc=storage.spacer_data_loc(
            settings.ROBOT_MODEL_VALRESULT_PATTERN.format(pk=classifier.pk))
    )

    # Assemble the message body.
    msg = JobMsg(task_name='train_classifier', tasks=[task])

    # Submit.
    queue = get_queue_class()()
    queue.submit_job(msg, job_id)

    logger.info(
        f"Submitted {classifier} with {classifier.nbr_train_images} images.")
    return msg


@job_starter(job_name='classify_image')
def deploy(api_job_id, api_unit_order, job_id):
    """ Submits a deploy job. """
    try:
        api_job_unit = ApiJobUnit.objects.get(
            parent_id=api_job_id, order_in_parent=api_unit_order)
    except ApiJobUnit.DoesNotExist:
        raise JobError(
            f"Job unit [{api_job_id} / {api_unit_order}] does not exist.")

    classifier_id = api_job_unit.request_json['classifier_id']
    try:
        classifier = Classifier.objects.get(pk=classifier_id)
    except Classifier.DoesNotExist:
        error_message = (
            f"Classifier of id {classifier_id} does not exist."
            f" Maybe it was deleted.")
        raise JobError(error_message)

    storage = get_storage_class()()

    task = ClassifyImageMsg(
        job_token=str(job_id),
        image_loc=DataLocation(
            storage_type='url',
            key=api_job_unit.request_json['url']
        ),
        feature_extractor_name=classifier.source.feature_extractor,
        rowcols=[(point['row'], point['column']) for point in
                 api_job_unit.request_json['points']],
        classifier_loc=storage.spacer_data_loc(
            settings.ROBOT_MODEL_FILE_PATTERN.format(pk=classifier.pk))
    )
    # Note the 'deploy' is called 'classify_image' in spacer.
    msg = JobMsg(task_name='classify_image', tasks=[task])

    # Submit.
    queue = get_queue_class()()
    queue.submit_job(msg, job_id)

    logger.info(
        f"Deploy submission made: ApiJobUnit {api_job_unit.pk},"
        f" Image URL [{api_job_unit.request_json['url']}]")

    return msg


@job_runner(job_name='classify_features')
def classify_image(image_id):
    """ Executes a classify_image job. """
    try:
        img = Image.objects.get(pk=image_id)
    except Image.DoesNotExist:
        raise JobError(f"Image {image_id} does not exist.")

    if not img.features.extracted:
        raise JobError(
            f"Image {image_id} needs to have features extracted"
            f" before being classified.")

    classifier = img.source.get_current_classifier()
    if not classifier:
        raise JobError(
            f"Image {image_id} can't be classified;"
            f" its source doesn't have a classifier.")

    # Create task message
    storage = get_storage_class()()
    msg = ClassifyFeaturesMsg(
        job_token=str(image_id),
        feature_loc=storage.spacer_data_loc(
            settings.FEATURE_VECTOR_FILE_PATTERN.format(
                full_image_path=img.original_file.name)),
        classifier_loc=storage.spacer_data_loc(
            settings.ROBOT_MODEL_FILE_PATTERN.format(pk=classifier.pk)
        )
    )

    # Process job right here since it is so fast.
    # In spacer, this task is called classify_features since that
    # is actually what we are doing (the feature are already extracted).
    res: ClassifyReturnMsg = spacer_classify_features(msg)

    # Pre-fetch label objects
    label_objs = [Label.objects.get(pk=pk) for pk in res.classes]

    # Add annotations if image isn't already confirmed    
    if not img.annoinfo.confirmed:
        try:
            th.add_annotations(image_id, res, label_objs, classifier)
        except IntegrityError:
            raise JobError(
                f"Failed to classify {img} with classifier {classifier.pk}."
                f" There might have been a race condition when trying"
                f" to save annotations."
            )

    # Always add scores
    th.add_scores(image_id, res, label_objs)

    img.features.classified = True
    img.features.save()

    return f"Used classifier {classifier.pk}"


@job_runner(interval=timedelta(minutes=1))
def collect_spacer_jobs():
    """
    Collects and handles spacer job results until A) the result queue is empty
    or B) the max job time has been reached.

    This task gets job-tracking to enforce that only one thread runs this
    task at a time. That way, no spacer job can get collected multiple times.
    """
    start = timezone.now()
    wrap_up_time = start + timedelta(minutes=settings.JOB_MAX_MINUTES)
    timed_out = False

    queue = get_queue_class()()
    job_statuses = []

    for job in queue.get_collectable_jobs():
        job_res, job_status = queue.collect_job(job)
        job_statuses.append(job_status)
        if job_res:
            th.handle_spacer_result(job_res)

        if timezone.now() > wrap_up_time:
            # As long as collect_jobs() is implemented with `yield`,
            # this loop-break won't abandon any job results.
            timed_out = True
            break

    status_counts = Counter(job_statuses)

    # sorted() sorts statuses alphabetically.
    counts_str = ', '.join([
        f'{count} {status}'
        for status, count in sorted(status_counts.items())
    ])
    result_str = f"Jobs collected: {counts_str or '0'}"

    if timed_out:
        result_str += " (timed out)"
    return result_str


@job_runner()
def reset_backend_for_source(source_id):
    """
    Removes all traces of the backend for this source, including
    classifiers and features.
    """
    queue_job(
        'reset_classifiers_for_source', source_id,
        source_id=source_id)

    for image in Image.objects.filter(source_id=source_id):
        reset_features(image)


@job_runner()
def reset_classifiers_for_source(source_id):
    """
    Removes all traces of the classifiers for this source, including:
    1) Delete all Score objects for all images
    2) Delete Classifier objects
    3) Sets all image.features.classified = False
    """
    Score.objects.filter(source_id=source_id).delete()
    Classifier.objects.filter(source_id=source_id).delete()
    Annotation.objects.filter(source_id=source_id).unconfirmed().delete()
    for image in Image.objects.filter(source_id=source_id):
        image.features.classified = False
        image.features.save()

    # Can probably train a new classifier.
    queue_source_check(source_id)
