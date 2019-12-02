import logging
import json
import pickle
from six import StringIO

from celery.decorators import task, periodic_task
from django.conf import settings
from django.db import IntegrityError
from django.core.files.storage import get_storage_class
from django.utils.timezone import now

from datetime import timedelta

import task_helpers as th

from .models import Classifier, Score
from annotations.models import Annotation
from images.models import Source, Image, Point
from labels.models import LabelSet, Label

from .backends import get_backend_class
from accounts.utils import get_robot_user

logger = logging.getLogger(__name__)


@task(name="Submit Features")
def submit_features(image_id, force=False):
    """
    Submits a job to SQS for extracting features for an image.
    """
    if settings.FORCE_NO_BACKEND_SUBMIT:
        logger.info(
            "VB task was called, but not run because backend submissions are"
            " off.")
        return

    try:
        img = Image.objects.get(pk=image_id)
    except:
        logger.info("Image {} does not exist.".format(image_id))
        return
    logstr = u"Image {} [Source: {} [{}]]".format(image_id, img.source, img.source_id)

    if img.features.extracted and not force:
        logger.info(u"{} already has features".format(logstr))
        return

    # Assemble row column information
    rowcols = []
    for point in Point.objects.filter(image=img).order_by('id'):
        rowcols.append([point.row, point.column])
    
    # Setup the job payload.
    storage = get_storage_class()()
    full_image_path = storage.path(img.original_file.name)
    payload = {
        'imkey': full_image_path,
        'outputkey': settings.FEATURE_VECTOR_FILE_PATTERN.format(full_image_path=full_image_path),
        'modelname': 'vgg16_coralnet_ver1',
        'rowcols': rowcols,
        'pk': image_id
    }

    # Assemble message body.
    messagebody = {
        'task': 'extract_features',
        'payload': payload
    }

    # Submit.
    backend = get_backend_class()()
    backend.submit_job(messagebody)

    logger.info(u"Submitted feature extraction for {}".format(logstr))
    logger.debug(u"Submitted feature extraction for {}. Message: {}".format(logstr, messagebody))
    return messagebody


@periodic_task(run_every=timedelta(hours = 24), name='Periodic Classifiers Submit', ignore_result=True)
def submit_all_classifiers():
    for source in Source.objects.filter():
        if source.need_new_robot():
            submit_classifier.delay(source.id)


@task(name="Submit Classifier")
def submit_classifier(source_id, nbr_images=1e5, force=False):

    if settings.FORCE_NO_BACKEND_SUBMIT:
        logger.info(
            "VB task was called, but not run because backend submissions are"
            " off.")
        return

    try:
        source = Source.objects.get(pk=source_id)
    except:
        logger.info("Can't find source [{}]".format(source_id))
        return
    
    if not source.need_new_robot() and not force:
        logger.info(u"Source {} [{}] don't need new classifier.".format(source.name, source.pk))
        return

    logger.info(u"Preparing new classifier for {} [{}].".format(source.name, source.pk))
    
    # Create new classifier model
    images = Image.objects.filter(source = source, confirmed = True, features__extracted = True)[:nbr_images]
    classifier = Classifier(source = source, nbr_train_images = len(images))
    classifier.save()

    # Write traindict to file storage
    storage = get_storage_class()()
    traindict = th._make_dataset([image for image in images if image.trainset])
    traindict_path = storage.path(settings.ROBOT_MODEL_TRAINDATA_PATTERN.format(pk = classifier.pk))
    storage.save(traindict_path, StringIO(json.dumps(traindict)))

    # Write valdict to file storage
    valdict = th._make_dataset([image for image in images if image.valset])
    valdict_path = storage.path(settings.ROBOT_MODEL_VALDATA_PATTERN.format(pk = classifier.pk))
    storage.save(valdict_path, StringIO(json.dumps(valdict)))
        
    # Prepare information for the message payload
    previous_classifiers = Classifier.objects.filter(source=source, valid=True) # This will not include the current.
    pc_models = [storage.path(settings.ROBOT_MODEL_FILE_PATTERN.format(pk=pc.pk)) for pc in previous_classifiers]
    pc_pks = [pc.pk for pc in previous_classifiers]  # Primary keys needed for collect task.

    # Create payload
    payload = {
        'model': storage.path(settings.ROBOT_MODEL_FILE_PATTERN.format(pk = classifier.pk)),
        'traindata': storage.path(settings.ROBOT_MODEL_TRAINDATA_PATTERN.format(pk = classifier.pk)),
        'valdata': storage.path(settings.ROBOT_MODEL_VALDATA_PATTERN.format(pk = classifier.pk)),
        'valresult': storage.path(settings.ROBOT_MODEL_VALRESULT_PATTERN.format(pk = classifier.pk)),
        'pk': classifier.pk,
        'nbr_epochs': settings.NBR_TRAINING_EPOCHS,
        'pc_models': pc_models,
        'pc_pks': pc_pks
    }

    # Assbmeble the message body.
    messagebody = {
        'task': 'train_classifier',
        'payload': payload
    }

    # Submit.
    backend = get_backend_class()()
    backend.submit_job(messagebody)

    logger.info(u"Submitted classifier for source {} [{}] with {} images.".format(source.name, source.id, len(images)))
    logger.debug(u"Submitted classifier for source {} [{}] with {} images. Message: {}".format(source.name, source.id, len(images), messagebody))
    return messagebody
 

@task(name="Classify Image")
def classify_image(image_id):

    try:
        img = Image.objects.get(pk=image_id)
    except:
        logger.info("Image {} does not exist.".format(image_id))
        return

    if not img.features.extracted:
        return    

    classifier = img.source.get_latest_robot()
    if not classifier:
        return

    # Load model
    storage = get_storage_class()()
    classifier_model_path = settings.ROBOT_MODEL_FILE_PATTERN.format(pk=classifier.pk)
    with storage.open(classifier_model_path) as classifier_model_file:
        classifier_model = pickle.load(classifier_model_file)

    feats_path = settings.FEATURE_VECTOR_FILE_PATTERN.format(full_image_path = img.original_file.name)
    with storage.open(feats_path) as feats_file:
        feats = json.load(feats_file)

    # Classify.
    scores = classifier_model.predict_proba(feats)

    # Pre-fetch label objects
    label_objs = []
    for _class in classifier_model.classes_:
        label_objs.append(Label.objects.get(pk = _class))

    # Add annotations if image isn't already confirmed    
    if not img.confirmed:
        try:
            th._add_annotations(image_id, scores, label_objs, classifier)
        except IntegrityError:
            logger.info(u"Failed to classify Image {} [Source: {} [{}] with classifier {}. There might have been a race condition when trying to save annotations. Will try again later.".format(img.id, img.source, img.source_id, classifier.id))
            classify_image.apply_async(args=[image_id], eta=now() + timedelta(seconds=10))
            return
    
    # Always add scores
    th._add_scores(image_id, scores, label_objs)
    
    img.features.classified = True
    img.features.save()

    logger.info(u"Classified Image {} [Source: {} [{}]] with classifier {}".format(img.id, img.source, img.source_id, classifier.id))


@periodic_task(run_every=timedelta(seconds=60), name='Collect all jobs', ignore_result=True)
def collect_all_jobs():
    """
    Collects and handles job results until the job result queue is empty.
    """
    logger.info('Collecting all jobs in result queue.')
    backend = get_backend_class()()
    while True:
        messagebody = backend.collect_job()
        if messagebody:
            _handle_job_result(messagebody)
        else:
            break
    logger.info('Done collecting all jobs in result queue.')


def _handle_job_result(messagebody):

    # Handle message
    pk = messagebody['original_job']['payload']['pk']
    task = messagebody['original_job']['task']

    if task == 'extract_features':
        if th._featurecollector(messagebody):
            # If job was entered into DB, submit a classify job.
            classify_image.apply_async(args=[pk], eta=now() + timedelta(seconds=10))

    elif task == 'train_classifier':
        if th._classifiercollector(messagebody):
            # If job was entered into DB, submit a classify job for all images in source.
            classifier = Classifier.objects.get(pk=pk)
            for image in Image.objects.filter(source=classifier.source, features__extracted=True, confirmed=False):
                classify_image.apply_async(args=[image.id], eta=now() + timedelta(seconds = 10))
    else:
        logger.error('Job task type {} not recognized'.format(task))

    # Conclude
    logger.info("job {}, pk: {} collected successfully".format(task, pk))
    logger.debug("Collected job with messagebody: {}".format(messagebody))


@task(name="Reset Source")
def reset_after_labelset_change(source_id):
    """
    The removes ALL TRACES of the vision backend for this source, including:
    1) Delete all Score objects for all images
    2) Delete Classifier objects
    3) Sets all image.features.classified = False
    """
    Score.objects.filter(source_id = source_id).delete()
    Classifier.objects.filter(source_id = source_id).delete()
    Annotation.objects.filter(source_id = source_id, user = get_robot_user()).delete()
    for image in Image.objects.filter(source_id = source_id):
        image.features.classified = False
        image.features.save()

    # Finally, let's train a new classifier.
    submit_classifier.apply_async(args = [source_id], eta = now() + timedelta(seconds = 10))


@task(name="Reset Features")
def reset_features(image_id):
    """
    Resets features for image. Call this after any change that affects the image 
    point locations. E.g:
    Re-generate point locations.
    Change annotation area.
    Add new poits.
    """

    img = Image.objects.get(pk = image_id)
    features = img.features
    features.extracted = False
    features.classified = False
    features.save()

    # Re-submit feature extraction.
    submit_features.apply_async(args = [img.id], eta = now() + timedelta(seconds = 10))




