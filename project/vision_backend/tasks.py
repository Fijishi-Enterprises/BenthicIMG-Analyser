import boto
import os
import json

from boto.s3.key import Key
from boto.sqs.message import Message

from django.conf import settings
from django.utils import timezone
from images.models import Source, Image, Point
from annotations.models import Annotation, LabelSet
from .models import Classifier


def features_submit(image_id):
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


def classifier_submit(source_id):

    source = Source.objects.get(pk = source_id)
    
    # Check if we really should try to train a new robot.
    if not source.need_new_robot():
        print "Source {} [{}] don't need a robot right now".format(source.name, source.pk)
        return

    # Create new classifier model
    images = Image.objects.filter(source = source, status__annotatedByHuman = True, features__extracted = True)
    train_images = [image for image in images if image.trainset]
    classifier = Classifier(source = source, nbr_train_images = len(images))
    classifier.save()

    # Store ground truth annotations and feature points in dictionary
    _write_dataset(classifier, 'trainset', settings.ROBOT_MODEL_TRAINDATA_PATTERN)
    _write_dataset(classifier, 'valset', settings.ROBOT_MODEL_VALDATA_PATTERN)
    
    # Prepare information for the message payload
    classes = [l.id for l in LabelSet.objects.get(source = source).labels.all()] # Needed for the classifier.
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
    


def _write_dataset(classifier, split, keypattern):
    """
    helper function for classifier_submit. Calls _make_dataset and then 
    writes the result to S3.
    """
    
    gtdict = _make_dataset(classifier, split)
    conn = boto.connect_s3(
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY
    )
    bucket = conn.get_bucket(settings.AWS_STORAGE_BUCKET_NAME)
    k = Key(bucket)
    k.key = keypattern.format(pk = classifier.pk, media = settings.AWS_S3_MEDIA_SUBDIR)
    k.set_contents_from_string(json.dumps(gtdict))


def _make_dataset(classifier, split):
    """
    Helper funtion for classifier_submit. Assemples all features and ground truth annotations
    for training and evaluation of the robot classifier.
    """

    images = Image.objects.filter(source = classifier.source, status__annotatedByHuman = True)
    train_images = [image for image in images if getattr(image, split)]

    gtdict = {}
    for img in train_images:
        full_image_path = os.path.join(settings.AWS_S3_MEDIA_SUBDIR, img.original_file.name)
        feature_key = settings.FEATURE_VECTOR_FILE_PATTERN.format(full_image_path = full_image_path)
        anns = Annotation.objects.filter(image = img).order_by('point__id')
        gtlabels = [ann.label.id for ann in anns]
        gtdict[feature_key] = gtlabels

    return gtdict


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
        'extract_features': _featurecollector,
        'train_classifier': _classifiercollector
    }


    # Collect the job
    if jobcollectors[messagebody['original_job']['task']](messagebody):
        print "job {}, pk: {} collected successfully".format(messagebody['original_job']['task'], messagebody['original_job']['payload']['pk'])
    else:
        print "some error occurred" #replace with logging.

    # Remove from queue        
    message.delete()

def _read_message(queue_name):
    """
    helper function for reading messages from AWS SQS.
    """

    conn = boto.sqs.connect_to_region("us-west-2",
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY)

    queue = conn.get_queue(queue_name)

    message = queue.read()
    if message is None:
        return None
    else:
        return message


def _featurecollector(messagebody):
    """
    collects feature_extract jobs.
    """
    try:
        img = Image.objects.get(pk = messagebody['original_job']['payload']['pk'])
    except:
        return 0

    # Double-check that the row-col information is still correct.
    rowcols = []
    for point in Point.objects.filter(image = img).order_by('id'):
        rowcols.append([point.row, point.column])

    if not rowcols == messagebody['original_job']['payload']['rowcols']:
        print "Row-col have changed. Throwing this message out."
        return 0
    
    # If all is ok store meta-data.
    img.features.extracted = True
    img.features.runtime_total = messagebody['result']['runtime']['total']
    img.features.runtime_core = messagebody['result']['runtime']['core']
    img.features.model_was_cashed = messagebody['result']['model_was_cashed']
    img.features.extracted_date = timezone.now()
    img.features.save()
    return 1

def _classifiercollector(messagebody):
    """
    collects train_classifier jobs.
    """
    result = messagebody['result']
    payload = messagebody['original_job']['payload']
    
    print result
    print payload

    # Check that Classifier still exists. 
    try:
        classifier = Classifier.objects.get(pk = payload['pk'])
    except:
        print "Classifier {} was deleted from database".format(payload['pk'])
        return 0

    # Check that the accuracy is higher than the previous classifiers
    if 'pc_models' in payload and len(payload['pc_models']) > 0:
        if max(result['pc_accs']) * settings.NEW_CLASSIFIER_IMPROVEMENT_TH > result['acc']:
            print "New model worse than previous. Classifier not validated."
            return 0
        
        # Update accuracy for previous models
        for pc_pk, pc_acc in zip(payload['pc_pks'], result['pc_accs']):
            pc = Classifier.objects.get(pk = pc_pk)
            pc.accuracy = pc_acc
            pc.save()
    
    classifier.valid = True
    classifier.runtime_train = result['runtime']
    classifier.accuracy = result['acc']
    classifier.epoch_ref_accuracy = str([int(round(100 * ra)) for ra in result['refacc']])
    classifier.save()
    return 1









