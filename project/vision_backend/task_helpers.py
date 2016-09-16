"""
This file contains helper functions to vision_backend.tasks.
"""
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

from .models import Classifier, Score
from images.models import Source, Image, Point


def _add_labels(image_id, scores, classes, classifier):
    print scores, classes, type(classes)
    user = get_robot_user()
    img = Image.objects.get(pk = image_id)
    points = Point.objects.filter(image = img).order_by('id')
    estlabels = [np.argmax(score) for score in scores]
    for pt, estlabel in zip(points, estlabels):
        
        label = Label.objects.get(pk = classes[estlabel])

        # If there's an existing annotation for this point, get it.
        # Otherwise, create a new annotation.
        try:
            anno = Annotation.objects.get(image=img, point=pt)

        except Annotation.DoesNotExist:
            # No existing annotation. Create a new one.
            new_anno = Annotation(
                image=img, label=label, point=pt,
                user=user, robot_version=classifier, source=img.source
            )
            #new_anno.save()

        else:
            # Got an existing annotation.
            if is_robot_user(anno.user):
                # It's an existing robot annotation. Update it as necessary.
                if anno.label.id != label.id:
                    anno.label = label
                    anno.robot_version = classifier
                    #anno.save()

            # Else, it's an existing confirmed annotation, and we don't want
            # to overwrite it. So do nothing in this case.

def _add_scores(image_id, scores, classes, classifier):
    """

    """
    img = Image.objects.get(pk = image_id)

    # First, delete all scores associated with this image.
    for score_obj in Score.objects.filter(image = img):
        score_obj.delete()

    points = Point.objects.filter(image = img).order_by('id')
    # Now, go through and create new ones.

    # Figure out how many of the (top) scores to store.
    n = np.min(NBR_SCORES_SCORED_PER_ANNOTATION, len(scores[0]))
    for point, score in zip(points, scores):
        inds = np.argsort(score)[::-1][:nbr_scores] # grab the index of the n highest index
        for ind in inds:
            score_obj = Score(
                source = img.source, 
                image = img, 
                label = Label.objects.get(pk = classes[ind]), 
                point = point, 
                score = int(round(score[ind]*100))
            )
            score_obj.save()

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

    images = Image.objects.filter(source = classifier.source, confirmed = True)
    train_images = [image for image in images if getattr(image, split)]

    gtdict = {}
    for img in train_images:
        full_image_path = os.path.join(settings.AWS_S3_MEDIA_SUBDIR, img.original_file.name)
        feature_key = settings.FEATURE_VECTOR_FILE_PATTERN.format(full_image_path = full_image_path)
        anns = Annotation.objects.filter(image = img).order_by('point__id')
        gtlabels = [ann.label.id for ann in anns]
        gtdict[feature_key] = gtlabels

    return gtdict


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




