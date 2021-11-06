import logging
from datetime import timedelta

from celery.decorators import task, periodic_task
from django.conf import settings
from django.core.files.storage import get_storage_class
from django.core.mail import mail_admins
from django.db import IntegrityError
from django.utils import timezone
from django.utils.timezone import now
from spacer.messages import \
    ExtractFeaturesMsg, \
    TrainClassifierMsg, \
    ClassifyFeaturesMsg, \
    ClassifyImageMsg, \
    ClassifyReturnMsg, \
    JobMsg, \
    JobReturnMsg, \
    DataLocation
from spacer.tasks import classify_features as spacer_classify_features

from accounts.utils import get_robot_user
from annotations.models import Annotation
from api_core.models import ApiJobUnit
from images.models import Source, Image, Point
from labels.models import Label
from . import task_helpers as th
from .models import Classifier, Score, BatchJob
from .queues import get_queue_class

logger = logging.getLogger(__name__)


@task(name="Submit Features")
def submit_features(image_id, force=False):
    """ Submits a feature extraction job. """

    try:
        img = Image.objects.get(pk=image_id)
    except Image.DoesNotExist:
        logger.info("Image {} does not exist.".format(image_id))
        return
    log_str = "Image {} [Source: {} [{}]]".format(image_id, img.source,
                                                   img.source_id)

    if img.features.extracted and not force:
        logger.info("{} already has features".format(log_str))
        return

    # Setup the job payload.
    storage = get_storage_class()()

    # Assemble row column information
    rowcols = [(p.row, p.column) for p in Point.objects.filter(image=img)]

    # Assemble task.
    task = ExtractFeaturesMsg(
        job_token=th.encode_spacer_job_token([image_id]),
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
    queue.submit_job(msg)

    logger.info("Submitted feature extraction for {}".format(log_str))
    return msg


@periodic_task(run_every=timedelta(hours=24),
               name='Periodic Classifiers Submit',
               ignore_result=True)
def submit_all_classifiers():
    for source in Source.objects.filter():
        if source.need_new_robot():
            submit_classifier.delay(source.id)


@task(name="Submit Classifier")
def submit_classifier(source_id, nbr_images=1e5, force=False):
    """ Submits a classifier training job. """
    try:
        source = Source.objects.get(pk=source_id)
    except Source.DoesNotExist:
        logger.info("Can't find source [{}]".format(source_id))
        return

    if not source.need_new_robot() and not force:
        logger.info("Source {} [{}] don't need new classifier.".format(
            source.name, source.pk))
        return

    # Create new classifier model
    images = Image.objects.filter(source=source,
                                  annoinfo__confirmed=True,
                                  features__extracted=True)[:nbr_images]
    classifier = Classifier(source=source, nbr_train_images=len(images))
    classifier.save()

    logger.info("Preparing new classifier ({}) for {} [{}].".format(
        classifier.pk, source.name, source.pk))

    # Create train-labels
    storage = get_storage_class()()
    train_labels = th.make_dataset([image for image in images if image.trainset])

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
        logger.info(
            f"Classifier {classifier.pk} for source {source.name}"
            f" [{source.pk}] was declined training, because the training"
            f" labelset ended up only having one unique label. Training"
            f" requires at least 2 unique labels.")
        return

    # This will not include the one we just created, b/c status isn't accepted.
    prev_classifiers = source.get_accepted_robots()

    # Primary keys needed for collect task.
    pc_pks = [pc.pk for pc in prev_classifiers]

    # Create TrainClassifierMsg
    task = TrainClassifierMsg(
        job_token=th.encode_spacer_job_token([classifier.pk] + pc_pks),
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
    queue.submit_job(msg)

    logger.info("Submitted classifier {} for source {} [{}] with {} images.".
                format(classifier.pk, source.name, source.id, len(images)))
    return msg


@task(name="Deploy")
def deploy(job_unit_id):
    """ Submits a deploy job. """
    try:
        job_unit = ApiJobUnit.objects.get(pk=job_unit_id)
    except ApiJobUnit.DoesNotExist:
        logger.info("Job unit of id {} does not exist.".format(job_unit_id))
        return

    job_unit.status = ApiJobUnit.IN_PROGRESS
    job_unit.save()

    classifier_id = job_unit.request_json['classifier_id']
    try:
        classifier = Classifier.objects.get(pk=classifier_id)
    except Classifier.DoesNotExist:
        error_message = (
            "Classifier of id {} does not exist. Maybe it was deleted."
            .format(classifier_id))
        job_unit.result_json = dict(
            url=job_unit.request_json['url'],
            errors=[error_message],
        )
        job_unit.status = ApiJobUnit.FAILURE
        job_unit.save()
        logger.error(error_message)
        return

    storage = get_storage_class()()

    task = ClassifyImageMsg(
        job_token=th.encode_spacer_job_token([job_unit_id]),
        image_loc=DataLocation(
            storage_type='url',
            key=job_unit.request_json['url']
        ),
        feature_extractor_name=classifier.source.feature_extractor,
        rowcols=[(point['row'], point['column']) for point in
                 job_unit.request_json['points']],
        classifier_loc=storage.spacer_data_loc(
            settings.ROBOT_MODEL_FILE_PATTERN.format(pk=classifier.pk))
    )
    # Note the 'deploy' is called 'classify_image' in spacer.
    msg = JobMsg(task_name='classify_image', tasks=[task])

    # Submit.
    queue = get_queue_class()()
    queue.submit_job(msg)

    logger.info("Submitted image at url: {} for deploy with job unit {}.".
                format(job_unit.request_json['url'], job_unit.pk))

    return msg


@task(name="Classify Image")
def classify_image(image_id):
    """ Executes a classify_image job. """
    try:
        img = Image.objects.get(pk=image_id)
    except Image.DoesNotExist:
        logger.info("Image {} does not exist.".format(image_id))
        return

    if not img.features.extracted:
        return

    classifier = img.source.get_latest_robot()
    if not classifier:
        return

    # Create task message
    storage = get_storage_class()()
    msg = ClassifyFeaturesMsg(
        job_token=th.encode_spacer_job_token([image_id]),
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
            logger_message = \
                "Failed to classify Image {} [Source: {} [{}] with " \
                "classifier {}. There might have been a race condition " \
                "when trying to save annotations. Will try again later."
            logger.info(logger_message.format(img.id, img.source,
                                              img.source_id, classifier.id))
            classify_image.apply_async(args=[image_id],
                                       eta=now() + timedelta(seconds=10))
            return

    # Always add scores
    th.add_scores(image_id, res, label_objs)

    img.features.classified = True
    img.features.save()

    logger.info("Classified Image {} [Source: {} [{}]] with classifier {}".
                format(img.id, img.source, img.source_id, classifier.id))


@periodic_task(run_every=timedelta(seconds=60), name='Collect all jobs',
               ignore_result=True)
def collect_all_jobs():
    """Collects and handles job results until the job result queue is empty."""

    logger.info('Collecting all jobs in result queue.')
    queue = get_queue_class()()
    while True:
        job_res = queue.collect_job()
        if job_res:
            _handle_job_result(job_res)
        else:
            break
    logger.info('Done collecting all jobs in result queue.')


def _handle_job_result(job_res: JobReturnMsg):
    """Handles the job results found in queue. """

    task_name = job_res.original_job.task_name

    if not job_res.ok:
        logger.error("Job failed: {}".format(job_res.error_message))

        if task_name == 'train_classifier':
            # train_fail() has its own logic for mailing admins.
            train_fail(job_res)
        elif task_name == 'classify_image':
            mail_admins("Spacer job failed", repr(job_res))
            deploy_fail(job_res)
        else:
            mail_admins("Spacer job failed", repr(job_res))

        return

    for task, res in zip(job_res.original_job.tasks,
                         job_res.results):
        pk = th.decode_spacer_job_token(task.job_token)[0]
        if task_name == 'extract_features':
            if th.featurecollector(task, res):
                # If job was entered into DB, submit a classify job.
                classify_image.apply_async(args=[pk],
                                           eta=now() + timedelta(seconds=10))

        elif task_name == 'train_classifier':
            if th.classifiercollector(task, res):
                # If successful, submit a classify job for all imgs in source.
                classifier = Classifier.objects.get(pk=pk)
                for image in Image.objects.filter(source=classifier.source,
                                                  features__extracted=True,
                                                  annoinfo__confirmed=False):
                    classify_image.apply_async(
                        args=[image.id],
                        eta=now() + timedelta(seconds=10))
        elif task_name == 'classify_image':
            th.deploycollector(task, res)

        else:
            logger.error('Job task type {} not recognized'.format(task_name))

        # Conclude
        logger.info("Collected job: {} with pk: {}".format(task_name, pk))


def train_fail(job_return_msg: JobReturnMsg):
    job_token = job_return_msg.original_job.tasks[0].job_token
    pk = th.decode_spacer_job_token(job_token)[0]

    try:
        classifier = Classifier.objects.get(pk=pk)
    except Classifier.DoesNotExist:
        # This should be an edge case, where the user reset the classifiers or
        # deleted the source before training could complete.
        logger.info(
            "Training failed for classifier {}, although the classifier"
            " was already deleted.".format(job_token))
        return

    classifier.status = Classifier.TRAIN_ERROR
    classifier.save()
    logger.info(
        "Training failed for classifier {}.".format(job_token))

    # Sometimes training fails because features were temporarily de-synced
    # with the points. We'll take different actions depending on the number of
    # train attempts that failed in a row.
    source = classifier.source
    last_classifiers = source.classifier_set.order_by('-pk')[:5]
    train_fails_in_a_row = 0
    for clf in last_classifiers:
        if clf.status == Classifier.TRAIN_ERROR:
            train_fails_in_a_row += 1
        else:
            break

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
        # Hopefully this eta is enough time for the features to get extracted,
        # regardless of image count.
        # (The "2 or 3" check attempts to cover for the case where train
        # number 3 happens very soon from submit_all_classifiers(), thus
        # leaving no time for feature extraction.)
        submit_classifier.apply_async(
            args=[source.pk],
            eta=now() + timedelta(hours=8))
    else:
        # 4 or more fails in a row. Notify the admins.
        mail_admins("Spacer job failed", repr(job_return_msg))
        # Next retrain happens when submit_all_classifiers() is run
        # (<= 24 hours).


def deploy_fail(job_return_msg: JobReturnMsg):

    pk = th.decode_spacer_job_token(
        job_return_msg.original_job.tasks[0].job_token)[0]
    try:
        job_unit = ApiJobUnit.objects.get(pk=pk)
    except ApiJobUnit.DoesNotExist:
        logger.info("Job unit of id {} does not exist.".format(pk))
        return

    job_unit.result_json = dict(
        url=job_unit.request_json['url'],
        errors=[job_return_msg.error_message],
    )
    job_unit.status = ApiJobUnit.FAILURE
    job_unit.save()


@task(name="Reset Source")
def reset_backend_for_source(source_id):
    """
    Removes all traces of the backend for this source, including
    classifiers and features.
    """
    reset_classifiers_for_source.apply_async(
        args=[source_id], eta=now() + timedelta(seconds=10))

    for image in Image.objects.filter(source_id=source_id):
        reset_features.apply_async(
            args=[image.pk], eta=now() + timedelta(seconds=10))


@task(name="Reset Classifiers")
def reset_classifiers_for_source(source_id):
    """
    Removes all traces of the classifiers for this source, including:
    1) Delete all Score objects for all images
    2) Delete Classifier objects
    3) Sets all image.features.classified = False
    """
    Score.objects.filter(source_id=source_id).delete()
    Classifier.objects.filter(source_id=source_id).delete()
    Annotation.objects.filter(source_id=source_id,
                              user=get_robot_user()).delete()
    for image in Image.objects.filter(source_id=source_id):
        image.features.classified = False
        image.features.save()

    # Finally, let's train a new classifier.
    submit_classifier.apply_async(args=[source_id],
                                  eta=now() + timedelta(seconds=10))


@task(name="Reset Features")
def reset_features(image_id):
    """
    Resets features for image. Call this after any change that affects
    the image point locations. E.g:
    Re-generate point locations.
    Change annotation area.
    Add new points.
    """

    try:
        img = Image.objects.get(pk=image_id)
    except Image.DoesNotExist:
        logger.info("Image {} deleted. Nothing to reset.".format(image_id))
        return

    features = img.features
    features.extracted = False
    features.classified = False
    features.save()

    # Re-submit feature extraction.
    submit_features.apply_async(args=[img.id],
                                eta=now() + timedelta(seconds=10))


@periodic_task(
    run_every=timedelta(days=1),
    name="Purge old batch jobs.",
    ignore_result=True,
)
def clean_up_old_batch_jobs():
    thirty_days_ago = timezone.now() - timedelta(days=30)
    for job in BatchJob.objects.filter(create_date__lt=thirty_days_ago):
        job.delete()


@periodic_task(
    run_every=timedelta(days=1),
    name="Alert if batch jobs did not succeed.",
    ignore_result=True,
)
def warn_about_stuck_jobs():
    """
    Warn about each stuck job that has crossed the 5 day mark. Since this
    task runs every day, only grab jobs between 5-6 days so we don't issue
    a repeat warning after 6 days, 7 days, etc.
    """
    five_days_ago = timezone.now() - timedelta(days=5)
    six_days_ago = five_days_ago - timedelta(days=1)
    stuck_jobs_between_5_and_6_days_old = BatchJob.objects \
        .filter(create_date__lt=five_days_ago, create_date__gt=six_days_ago) \
        .exclude(status='SUCCEEDED') \
        .exclude(status='FAILED')
    for job in stuck_jobs_between_5_and_6_days_old:
        mail_admins("Job {} not completed after 5 days.".format(
            job.batch_token), str(job))
