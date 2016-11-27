"""
This file contains helper functions to vision_backend.tasks.
"""
import boto.sqs
import os
import json
import logging

import numpy as np

from sklearn import linear_model

from django.conf import settings
from django.utils import timezone
from django.db.models import F
from django.db import transaction
from reversion import revisions

from images.models import Image, Point
from annotations.models import Annotation
from accounts.utils import get_robot_user, is_robot_user

from .models import Classifier, Score

logger = logging.getLogger(__name__)

def _submit_job(messagebody):
    """
    Submits message to the SQS spacer_jobs
    """
    conn = boto.sqs.connect_to_region("us-west-2",
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY)
    queue = conn.get_queue('spacer_jobs')
    m = boto.sqs.message.Message()
    m.set_body(json.dumps(messagebody))
    queue.write(m)


# Must explicitly turn on history creation when RevisionMiddleware is
# not in effect. (It's only in effect within views.)
@revisions.create_revision()
def _add_annotations(image_id, scores, label_objs, classifier):
    """
    Adds annotations objects using the classifier scores.
    NOTE: this function is SLOW.
    """
    user = get_robot_user()
    img = Image.objects.get(pk = image_id)
    points = Point.objects.filter(image = img).order_by('id')
    estlabels = [np.argmax(score) for score in scores]
    anno_objs = []
    with transaction.atomic():
        for pt, estlabel in zip(points, estlabels):
            
            label = label_objs[estlabel]

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
                new_anno.save()

            else:
                # Got an existing annotation.
                if is_robot_user(anno.user):
                    # It's an existing robot annotation. Update it as necessary.
                    if anno.label.id != label.id:
                        anno.label = label
                        anno.robot_version = classifier
                        anno.save()

                # Else, it's an existing confirmed annotation, and we don't want
                # to overwrite it. So do nothing in this case.

def _add_scores(image_id, scores, label_objs):
    """
    Adds score objects using the classifier scores. 
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
                    label = label_objs[ind],
                    point = point, 
                    score = int(round(score[ind]*100))
                )
            )
    Score.objects.bulk_create(score_objs)


def _make_dataset(images):
    """
    Helper funtion for classifier_submit. Assemples all features and ground truth annotations
    for training and evaluation of the robot classifier.
    """
    gtdict = {}
    for img in images:
        full_image_path = os.path.join(settings.AWS_LOCATION, img.original_file.name)
        feature_key = settings.FEATURE_VECTOR_FILE_PATTERN.format(full_image_path = full_image_path)
        anns = Annotation.objects.filter(image = img).order_by('point__id').annotate(gt = F('label__id'))
        gtlabels = [int(ann.gt) for ann in anns]
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
    image_id = messagebody['original_job']['payload']['pk']
    try:
        img = Image.objects.get(pk = image_id)
    except:
        logger.info("Image {} was deleted. Aborting".format(image_id))
        return 0
    logstr = "Image {} [Source: {} [{}]]".format(image_id, img.source, img.source_id)
        
    # Double-check that the row-col information is still correct.
    rowcols = []
    for point in Point.objects.filter(image = img).order_by('id'):
        rowcols.append([point.row, point.column])

    if not rowcols == messagebody['original_job']['payload']['rowcols']:
        logger.info("Row-col for {} have changed. Aborting.".format(logstr))
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
    classifier.epoch_ref_accuracy = str([int(round(100 * ra)) for ra in result['refacc']])
    classifier.save()

    # Check that the accuracy is higher than the previous classifiers
    if 'pc_models' in payload and len(payload['pc_models']) > 0:
        if max(result['pc_accs']) * settings.NEW_CLASSIFIER_IMPROVEMENT_TH > result['acc']:
            logger.info("{} worse than previous. Not validated. Max previous: {0:.2f}, threshold: {0:.2f}, this: {0:.2f}".format(logstr, max(result['pc_accs']), max(result['pc_accs']) * settings.NEW_CLASSIFIER_IMPROVEMENT_TH, result['acc']))
            return 0
        
        # Update accuracy for previous models
        for pc_pk, pc_acc in zip(payload['pc_pks'], result['pc_accs']):
            pc = Classifier.objects.get(pk = pc_pk)
            pc.accuracy = pc_acc
            pc.save()
    
    classifier.valid = True
    classifier.save()
    logger.info("{} collected successfully.".format(logstr))
    return 1




