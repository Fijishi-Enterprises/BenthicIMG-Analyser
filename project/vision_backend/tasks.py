import os
import logging
import json

import numpy as np

from celery.decorators import task, periodic_task
from sklearn import linear_model
from datetime import timedelta

import task_helpers as th

from .models import Classifier, Score
from annotations.models import Annotation
from images.models import Source, Image, Point
from labels.models import LabelSet, Label

from lib.utils import direct_s3_read, direct_s3_write
from accounts.utils import get_robot_user

from django.conf import settings

import time

logger = logging.getLogger(__name__)


"""
Dummy tasks for debugging
"""

@task(name="one hello")
def one_hello_world():
    print "This is a one time hello world"

@periodic_task(run_every=timedelta(seconds = 10), name='periodic hello', ignore_result=True)
def hello_world():
    print "This is a periodic hello world"

@periodic_task(run_every=timedelta(seconds = 12), name='DB read', ignore_result=True)
def hello_world():
    print "There are {} images in the DB".format(Image.objects.filter().count())

"""
End dummy tasks for debugging
"""

@task(name = "submit_features")
def submit_features(image_id, force = False):
    """
    Submits a job to SQS for extracting features for an image.
    """
    # Do some initial checks
    if not hasattr(settings, 'AWS_S3_MEDIA_SUBDIR'):
        logger.info("Can't use vision backend if media is stored locally.")
        return

    try:
        img = Image.objects.get(pk = image_id)
    except:
        logger.info("Image {} does not exist.".format(image_id))
        return

    if img.features.extracted and not force:
        logger.info("Image {} already has features".format(image_id))
        return

    # Assemble row column information
    rowcols = []
    for point in Point.objects.filter(image = img).order_by('id'):
        rowcols.append([point.row, point.column])
    
    # Setup the job payload.
    full_image_path = os.path.join(settings.AWS_S3_MEDIA_SUBDIR, img.original_file.name)
    payload = {
        'bucketname': settings.AWS_STORAGE_BUCKET_NAME,
        'imkey': full_image_path,
        'outputkey': settings.FEATURE_VECTOR_FILE_PATTERN.format(full_image_path = full_image_path),
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
    th._submit_job(messagebody)

    logger.info("Submitted feature extraction for image {} [source: {}]. Message: {}".format(image_id, img.source_id, messagebody))


@task(name = "submit_classifier")
def submit_classifier(source_id, nbr_images = 1e5, force = False):

    # Do some intial checks
    if not hasattr(settings, 'AWS_S3_MEDIA_SUBDIR'):
        logger.info("Can't use vision backend if media is stored locally.")
        return

    try:
        source = Source.objects.get(pk = source_id)
    except:
        logger.info("Can't find source [{}]".format(source_id))
        return
    
    if not source.need_new_robot() and not force:
        logger.info("Source {} [{}] don't need new classifier.".format(source.name, source.pk))
        return

    logger.info("Preparing new classifier for {} [{}].".format(source.name, source.pk))    
    
    # Create new classifier model
    images = Image.objects.filter(source = source, confirmed = True, features__extracted = True)[:nbr_images]
    classifier = Classifier(source = source, nbr_train_images = len(images))
    classifier.save()

    # Write traindict to S3
    direct_s3_write(
        settings.ROBOT_MODEL_TRAINDATA_PATTERN.format(pk = classifier.pk, media = settings.AWS_S3_MEDIA_SUBDIR),
        'json',
        th._make_dataset([image for image in images if image.trainset])
    )

    # Write valdict to S3
    direct_s3_write(
        settings.ROBOT_MODEL_VALDATA_PATTERN.format(pk = classifier.pk, media = settings.AWS_S3_MEDIA_SUBDIR),
        'json',
        th._make_dataset([image for image in images if image.valset])
    )
        
    # Prepare information for the message payload
    classes = [l.global_label_id for l in LabelSet.objects.get(source = source).get_labels()] # Needed for the classifier.
    previous_classifiers = Classifier.objects.filter(source = source, valid = True) # This will not include the current.
    pc_models = [settings.ROBOT_MODEL_FILE_PATTERN.format(pk = pc.pk, media = settings.AWS_S3_MEDIA_SUBDIR) for pc in previous_classifiers]
    pc_pks = [pc.pk for pc in previous_classifiers] # Primary keys needed for collect task.

    # Create payload
    payload = {
        'bucketname': settings.AWS_STORAGE_BUCKET_NAME,
        'model': settings.ROBOT_MODEL_FILE_PATTERN.format(pk = classifier.pk, media = settings.AWS_S3_MEDIA_SUBDIR),
        'traindata': settings.ROBOT_MODEL_TRAINDATA_PATTERN.format(pk = classifier.pk, media = settings.AWS_S3_MEDIA_SUBDIR),
        'valdata': settings.ROBOT_MODEL_VALDATA_PATTERN.format(pk = classifier.pk, media = settings.AWS_S3_MEDIA_SUBDIR),
        'valresult': settings.ROBOT_MODEL_VALRESULT_PATTERN.format(pk = classifier.pk, media = settings.AWS_S3_MEDIA_SUBDIR),
        'pk': classifier.pk,
        'classes': classes,
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
    th._submit_job(messagebody)

    logger.info("Submitted classifier for source {} [{}] with {} images. Message: {}".format(source.name, source.id, len(images), messagebody))
 

@task(name = "classify_image")
def classify_image(image_id):


    # Do some initial checks
    if not hasattr(settings, 'AWS_S3_MEDIA_SUBDIR'):
        logger.info("Can't use vision backend if media is stored locally.")
        return

    try:
        img = Image.objects.get(pk = image_id)
    except:
        logger.info("Image {} does not exist.".format(image_id))
        return

    classifier = img.source.get_latest_robot()
    if not classifier:
        logger.info("No classifier exists for image {} [source {}]".format(img.id, img.source_id))
        return

    # Load model
    classifier_model = direct_s3_read(
        settings.ROBOT_MODEL_FILE_PATTERN.format(pk = classifier.pk, media = settings.AWS_S3_MEDIA_SUBDIR),
        'pickle' )
    
    feats = direct_s3_read(
        settings.FEATURE_VECTOR_FILE_PATTERN.format(full_image_path = os.path.join(settings.AWS_S3_MEDIA_SUBDIR, img.original_file.name)),
        'json' )

    # Classify
    scores = classifier_model.predict_proba(feats)

    # Pre-fetch label objects
    label_objs = []
    for _class in classifier_model.classes_:
        label_objs.append(Label.objects.get(pk = _class))

    # Add annotations if image isn't already confirmed    
    if not img.confirmed:
        th._add_annotations(image_id, scores, label_objs, classifier)
    
    # Always add scores
    th._add_scores(image_id, scores, label_objs)
    
    img.features.classified = True
    img.features.save()

    logger.info("Classified image {} [source {}] with classifier {}".format(img.id, img.source_id, classifier.id))


#@periodic_task(run_every=timedelta(seconds = 60), name='Collect all jobs', ignore_result=True)
def collect_all_jobs():
    """
    Runs collectjob until queue is empty.
    """
    logger.info('Collecting all jobs in result queue.')
    while collectjob():
        pass
    logger.info('Done collecting all jobs in result queue.')

@task(name = "collectjob")
def collectjob():
    """
    main task for collecting jobs from AWS SQS.
    """
    
    # Grab a message
    message = th._read_message('spacer_results')
    if message is None:
        return 0
    messagebody = json.loads(message.get_body())

    # Check that the message pertains to this server
    if not messagebody['original_job']['payload']['bucketname'] == settings.AWS_STORAGE_BUCKET_NAME:
        logger.info("Job pertains to wrong bucket [%]".format(messagebody['original_job']['payload']['bucketname']))
        return 1

    # Delete message (at this point, if it is not handeled correctly, we still want to delete it from queue.)
    message.delete()

    # Handle message
    pk = messagebody['original_job']['payload']['pk']
    task = messagebody['original_job']['task']
    
    if task == 'extract_features':
        if th._featurecollector(messagebody): 
            # If job was entered into DB, submit a classify job.
            classify_image.delay(pk)
            submit_classifier.delay(Image.objects.get(id = pk).source_id)
    elif task == 'train_classifier':
        if th._classifiercollector(messagebody):
            # If job was entered into DB, submit a classify job for all images in source.
            for image in Image.objects.filter(source_id = pk):
                classify_image.delay(image.id)

    else:
        logger.error('Job task type {} not recognized'.format(task))
    
    # Conclude
    logger.info("job {}, pk: {} collected successfully".format(task, pk))
    return 1


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

    # Finally, let's try to train a new classifier.
    submit_classifier.delay(source_id)

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
    submit_features.delay(image_id)




