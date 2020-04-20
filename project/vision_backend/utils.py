from __future__ import division

import boto

import numpy as np

from django.conf import settings

from lib.utils import direct_s3_read, direct_s3_write

from images.models import Source, Point
from labels.models import Label, LocalLabel
from .models import Classifier, Score


def acc(gt, est):
    """
    Calculate the accuracy of (agreement between) two interger valued list.
    """
    if len(gt) < 1:
        return 1
    else:
        return sum([(g == e) for (g,e) in zip(gt, est)]) / len(gt)


def get_label_scores_for_point(point, ordered=False):
    """
    :param point: The Point object to get label scores for. Only the top
        NBR_SCORES_PER_ANNOTATION scores are available for each point.
    :param ordered: If True, return the scores in descending order of score
        value. If False, return in arbitrary order (for performance).
    :return: {'label': <label code>, 'score': <score number>} for each Score
        available for this Point.
    """
    scores = Score.objects.filter(point=point)
    if ordered:
        scores = scores.order_by('-score')
    return [
        {'label': score.label_code, 'score': score.score}
        for score in scores
    ]


def get_label_scores_for_image(image_id):
    """
    Return all the saved label scores for an image in this format:
    {1: [{'label': 'Acrop', 'score': 14},
         {'label': 'Porit', 'score': 21},
         ...],
     2: [...], ...}
    Where the top-level dict's keys are the point numbers.
    """
    lpdict = {}
    for point in Point.objects.filter(image_id = image_id).order_by('id'):
        lpdict[point.point_number] = get_label_scores_for_point(point)
    return lpdict


def get_alleviate(estlabels, gtlabels, scores):
    """
    calculates accuracy for (up to) 250 different score thresholds.
    """
    if not len(estlabels) == len(gtlabels) or not len(estlabels) == len(scores):
        raise ValueError('all inputs must have the same length')

    if len(estlabels) == 0:
        raise ValueError('inputs must have length > 0')
    
    # convert to numpy for easy indexing
    scores, gtlabels, estlabels = np.asarray(scores), np.asarray(gtlabels, dtype=np.int), np.asarray(estlabels, dtype=np.int)
    
    # figureout appropritate thresholds to use
    ths = sorted(scores)

    # append something slightly lower and higher to ensure we include ratio = 0 and 100%
    ths.insert(0, max(min(ths) - 0.01, 0))
    ths.append(min(max(ths) + 0.01, 1.00))
    
    ths = np.asarray(ths) # convert back to numpy.
    # cap at 250
    if len(ths) > 250:
        ths = ths[np.linspace(0, len(ths) - 1, 250, dtype = np.int)] # max 250!
    
    # do the actual sweep.
    accs, ratios = [], []
    for th in ths:
        keep_ind = scores > th
        accs.append(round(100 * acc(estlabels[keep_ind], gtlabels[keep_ind]), 1))
        ratios.append(round(100 * np.sum(keep_ind) / len(estlabels), 1))
    ths = [round(100 * th, 1) for th in ths]
    
    return accs, ratios, ths


def map_labels(labellist, classmap):
    """
    Helper function to map integer labels to new labels.
    """
    labellist = np.asarray(labellist, dtype = np.int)
    newlist = -1 * np.ones(len(labellist), dtype = np.int)
    for key in classmap.keys():
        newlist[labellist == key] = classmap[key]
    return list(newlist)


def labelset_mapper(labelmode, classids, source):
    """
    Prepares mapping function and labelset names to inject in confusion matrix.
    """
    if labelmode == 'full':
        
        # The label names are the abbreviated full names with code in parethesis.
        classnames = [Label.objects.get(id = classid).name for classid in classids]
        codes = [LocalLabel.objects.get(global_label__id = classid, labelset = source.labelset).code for classid in classids]
        classmap = dict()
        for i in range(len(classnames)):
            if len(classnames[i]) > 30:
                classnames[i] = classnames[i][:27] + '...'
            classnames[i] = classnames[i] + ' (' + codes[i] + ')'
            classmap[i] = i

    elif labelmode == 'func':
        classmap = dict()
        classnames = []
        for classid in classids:
            fcnname = Label.objects.get(pk = classid).group.name
            if not fcnname in classnames:
                classnames.append(fcnname)
            classmap[classids.index(classid)] = classnames.index(fcnname)
    
    else:
        raise Exception('labelmode {} not recognized'.format(labelmode))

    return classmap, classnames


def get_total_messages_in_jobs_queue():
    """
    Returns number of jobs in the spacer jobs queue.
    If there are, for some tests, it means we have to wait.
    """
    if not settings.DEFAULT_FILE_STORAGE == 'lib.storage_backends.MediaStorageS3':
        return 0
    c = boto.sqs.connect_to_region('us-west-2')
    queue = c.lookup('spacer_jobs')
    attr = queue.get_attributes()
    return int(attr['ApproximateNumberOfMessages']) + int(attr['ApproximateNumberOfMessagesNotVisible'])



