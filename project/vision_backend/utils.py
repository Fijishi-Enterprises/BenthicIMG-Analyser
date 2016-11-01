import scipy.signal
import scipy.interpolate

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
        return float(sum([(g == e) for (g,e) in zip(gt, est)])) / len(gt)


def get_label_probabilities_for_image(image_id):
    """
    Returns the full label probabilities for an image in this format:
    {1: [{'label':'Acrop', 'score':0.148928}, {'label': Porit', 'score': 0.213792}, ...], 2: [...], ...}
    """
    lpdict = {}
    for point in Point.objects.filter(image_id = image_id).order_by('id'):
        lpdict[point.point_number] = []
        for score in Score.objects.filter(point = point):
            lpdict[point.point_number].append({'label': score.label_code, 'score':score.score})
    return lpdict


def get_alleviate(estlabels, gtlabels, scores):
    """
    calculates accuracy for (up to) 250 different score thresholds.
    """
    
    # convert to numpy for easy indexing
    scores, gtlabels, estlabels = np.asarray(scores), np.asarray(gtlabels, dtype=np.int), np.asarray(estlabels, dtype=np.int)
    
    # figureout appropritate thresholds to use
    ths = sorted(scores)
    if len(ths) > 250:
        ths = ths[np.linspace(0, len(ths) - 1, 250, dtype = np.int)] # max 250!
    # append something slightly lower and higher to ensure we include ratio = 0 and 100%
    ths.insert(0, max(min(ths) - 0.01, 0))
    ths.append(min(max(ths) + 0.01, 1.00))
    
    # do the actual sweep.
    accs, ratios = [], []
    for th in ths:
        keep_ind = scores > th
        accs.append(round(100 * acc(estlabels[keep_ind], gtlabels[keep_ind]), 1))
        ratios.append(round(100 * np.sum(keep_ind) / float(len(estlabels)), 1))
    ths = [round(100 * th, 1) for th in ths]
    
    return accs, ratios, ths


def map_labels(labellist, classmap):
    """
    Helper function to map integer labels to new labels.
    """
    labellist = np.asarray(labellist, dtype = np.int)
    newlist = np.zeros(len(labellist), dtype = np.int)
    for key in classmap.keys():
        newlist[labellist == key] = classmap[key]
    return list(newlist)

def labelset_mapper(labelmode, classids, source):
    """
    Prepares mapping function and labelset names to inject in confusion matrix.
    """
    if labelmode == 'full':
        
        # The label names are the abbreviated full names with code in parethesis.
        classnames = [LocalLabel.objects.get(global_label__id = classid, labelset = source.labelset).global_label.name for classid in classids]
        codes = [LocalLabel.objects.get(global_label__id = classid, labelset = source.labelset).code for classid in classids]
        classmap = dict()
        for i in range(len(classnames)):
            if len(classnames[i]) > 25:
                classnames[i] = classnames[i][:22] + '...'
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
        Exception('labelmode {} not recognized'.format(labelmode))

    return classmap, classnames