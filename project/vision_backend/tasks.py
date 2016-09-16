import boto
import os
import json
import pickle

import numpy as np

from sklearn import linear_model

from boto.s3.key import Key
from boto.sqs.message import Message



from django.conf import settings
from django.utils import timezone

from .models import Classifier, Score

from images.models import Source, Image, Point
from annotations.models import Annotation
from labels.models import LabelSet, Label
from accounts.utils import get_robot_user, is_robot_user

from . import task_helpers as th

def submit_features(image_id):
    """
    Submits a job to SQS for extracting features for an image.
    """

    img = Image.objects.get(pk = image_id)

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

    # Assbmeble the message body.
    messagebody = {
        'task': 'extract_features',
        'payload': payload
    }

    # Submit.
    conn = boto.sqs.connect_to_region("us-west-2",
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY)
    queue = conn.get_queue('spacer_jobs')
    m = Message()
    m.set_body(json.dumps(messagebody))
    queue.write(m)


def submit_classifier(source_id):

    source = Source.objects.get(pk = source_id)
    
    # Check if we really should try to train a new robot.
    if not source.need_new_robot():
        print "Source {} [{}] don't need a robot right now".format(source.name, source.pk)
        return

    # Create new classifier model
    images = Image.objects.filter(source = source, confirmed = True, features__extracted = True)
    train_images = [image for image in images if image.trainset]
    classifier = Classifier(source = source, nbr_train_images = len(images))
    classifier.save()

    # Store ground truth annotations and feature points in dictionary
    th._write_dataset(classifier, 'trainset', settings.ROBOT_MODEL_TRAINDATA_PATTERN)
    th._write_dataset(classifier, 'valset', settings.ROBOT_MODEL_VALDATA_PATTERN)
    
    # Prepare information for the message payload
    classes = [l.id for l in LabelSet.objects.get(source = source).get_labels()] # Needed for the classifier.
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

    print messagebody
    # Submit.
    conn = boto.sqs.connect_to_region("us-west-2",
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY)
    queue = conn.get_queue('spacer_jobs')
    m = Message()
    m.set_body(json.dumps(messagebody))
    queue.write(m)
 

def classify_image(image_id):
    try:
        img = Image.objects.get(pk = image_id)
    except:
        print "Image removed. Returning."
        return
    
    # Do some checks
    if not img.features.extracted:
        return
    classifier = img.source.get_latest_robot()
    if not classifier:
        return 0

    # Connect to S3
    conn = boto.connect_s3(
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY
    )
    bucket = conn.get_bucket(settings.AWS_STORAGE_BUCKET_NAME)
    
    # Load model
    k = Key(bucket)
    k.key = settings.ROBOT_MODEL_FILE_PATTERN.format(pk = classifier.pk, media = settings.AWS_S3_MEDIA_SUBDIR)
    classifier_model = pickle.loads(k.get_contents_as_string())
    
    # Load features
    k.key = settings.FEATURE_VECTOR_FILE_PATTERN.format(full_image_path = os.path.join(settings.AWS_S3_MEDIA_SUBDIR, img.original_file.name))
    feats = json.loads(k.get_contents_as_string())

    # Classify (very easy!)
    print 'feats', len(feats), len(feats[0])
    print 'classifier_model', classifier_model
    scores = classifier_model.predict_proba(feats)

    # Add annotations if image isn't already confirmed
    if not img.confirmed:
        th._add_labels(image_id, scores, classifier_model.classes_, classifier)
    
    # Always add scores
    th._add_scores(image_id, scores, classifier_model.classes_, classifier)



def collectjob():
    """
    main task for collecting jobs from AWS SQS.
    """
    
    # Grab a message
    message = _read_message('spacer_results')
    if message is None:
        print "No messages in queue."
        return
    messagebody = json.loads(message.get_body())

    # Check that the message pertains to this server
    if not messagebody['original_job']['payload']['bucketname'] == settings.AWS_STORAGE_BUCKET_NAME:
        return

    jobcollectors = {
        'extract_features': th._featurecollector,
        'train_classifier': th._classifiercollector
    }

    # Collect the job
    if jobcollectors[messagebody['original_job']['task']](messagebody):
        print "job {}, pk: {} collected successfully".format(messagebody['original_job']['task'], messagebody['original_job']['payload']['pk'])
    else:
        print "some error occurred" #replace with logging.

    # Remove from queue        
    message.delete()


def reset_after_labelset_change(source_id):
    """
    The removes ALL TRACES of the vision backend for this source, including:
    1) Delete all Score objects for all images
    2) Delete Classifier objects
    3) Sets all image.features.classified = False
    """
    Score.objects.filter(source_id = source_id).delete()
    Classifier.objects.filter(source_id = source_id).delete()
    for image in Image.objects.filter(source_id = source_id):
        image.features.classified = False
        image.features.save()

    # Finally, let's try to train a new classifier.
    submit_classifier(source_id)

def reset_featured(image_id):

    img = Image.objects.get(pk = image_id)
    features = img.features
    features.extracted = False
    features.classified = False
    features.save()

    # Re-submit feature extraction.
    submit_features(image_id)




