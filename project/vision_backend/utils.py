from django.conf import settings
import numpy as np
from spacer.extract_features import (
    DummyExtractor,
    EfficientNetExtractor,
    FeatureExtractor,
    VGG16CaffeExtractor,
)
from spacer.messages import DataLocation

from images.models import Point
from jobs.utils import queue_job
from labels.models import Label, LocalLabel
from .common import Extractors
from .models import Score


def acc(gt, est):
    """
    Calculate the accuracy of (agreement between) two interger valued list.
    """
    if len(gt) < 1:
        return 1
    else:
        return sum([(g == e) for (g, e) in zip(gt, est)]) / len(gt)


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
    for point in Point.objects.filter(image_id=image_id).order_by('id'):
        lpdict[point.point_number] = get_label_scores_for_point(point)
    return lpdict


def get_alleviate(estlabels, gtlabels, scores):
    """
    calculates accuracy for (up to) 250 different score thresholds.
    """
    if not len(estlabels) == len(gtlabels) or \
            not len(estlabels) == len(scores):
        raise ValueError('all inputs must have the same length')

    if len(estlabels) == 0:
        raise ValueError('inputs must have length > 0')
    
    # convert to numpy for easy indexing
    scores = np.asarray(scores)
    gtlabels = np.asarray(gtlabels, dtype=int)
    estlabels = np.asarray(estlabels, dtype=int)
    
    # Figure out teh appropriate thresholds to use
    ths = sorted(scores)

    # Append something slightly lower and higher to ensure we
    # include ratio = 0 and 100%
    ths.insert(0, max(min(ths) - 0.01, 0))
    ths.append(min(max(ths) + 0.01, 1.00))
    
    ths = np.asarray(ths)  # Convert back to numpy.
    # cap at 250
    if len(ths) > 250:
        ths = ths[np.linspace(0, len(ths) - 1, 250, dtype=int)]  # max 250!
    
    # do the actual sweep.
    accs, ratios = [], []
    for th in ths:
        keep_ind = scores > th
        this_acc = acc(estlabels[keep_ind], gtlabels[keep_ind])
        accs.append(round(100 * this_acc, 1))
        ratios.append(round(100 * np.sum(keep_ind) / len(estlabels), 1))
    ths = [round(100 * th, 1) for th in ths]
    
    return accs, ratios, ths


def map_labels(labellist, classmap):
    """
    Helper function to map integer labels to new labels.
    """
    labellist = np.asarray(labellist, dtype=int)
    newlist = -1 * np.ones(len(labellist), dtype=int)
    for key in classmap.keys():
        newlist[labellist == key] = classmap[key]
    return list(newlist)


def labelset_mapper(labelmode, classids, source):
    """
    Prepares mapping function and labelset names to inject in confusion matrix.
    """
    if labelmode == 'full':
        
        # Label names are the abbreviated full names with code in parethesis.
        classnames = [Label.objects.get(id=classid).name
                      for classid in classids]
        codes = [LocalLabel.objects.get(global_label__id=class_id,
                                        labelset=source.labelset).code
                 for class_id in classids]
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
            fcnname = Label.objects.get(pk=classid).group.name
            if fcnname not in classnames:
                classnames.append(fcnname)
            classmap[classids.index(classid)] = classnames.index(fcnname)
    
    else:
        raise Exception('labelmode {} not recognized'.format(labelmode))

    return classmap, classnames


def clear_features(image):
    """
    Clears features for image. Call this after any change that affects
    the image point locations. E.g:
    Re-generate point locations.
    Change annotation area.
    Add new points.
    """
    image.refresh_from_db()

    features = image.features
    features.extracted = False
    features.save()


def reset_features(image):
    clear_features(image)
    # Try to re-extract features
    queue_source_check(image.source_id)


def queue_source_check(source_id, delay=None):
    """
    Site views should generally call this function if they want to initiate
    any feature extraction, training, or classification.
    They should not call those three tasks directly. Let check_source()
    decide what needs to be run in what order.

    Site views generally shouldn't worry about specifying a delay, since this
    check_source Job only becomes visible to huey tasks when the view
    finishes its transaction. However, if desired, they can specify a delay.
    """
    return queue_job(
        'check_source',
        source_id,
        source_id=source_id,
        delay=delay,
    )


def get_extractor(extractor_choice: Extractors) -> FeatureExtractor:
    """
    For simplicity, the only extractor files supported here are the ones
    living in S3. So if not using AWS credentials, then need to use the
    dummy extractor.
    """
    match extractor_choice:
        case Extractors.EFFICIENTNET.value:
            return EfficientNetExtractor(
                data_locations=dict(
                    weights=DataLocation(
                        storage_type='s3',
                        key='efficientnet_b0_ver1.pt',
                        bucket_name=settings.EXTRACTORS_BUCKET,
                    ),
                ),
                data_hashes=dict(
                    weights='c3dc6d304179c6729c0a0b3d4e60c728'
                            'bdcf0d82687deeba54af71827467204c',
                ),
            )
        case Extractors.VGG16.value:
            return VGG16CaffeExtractor(
                data_locations=dict(
                    definition=DataLocation(
                        storage_type='s3',
                        key='vgg16_coralnet_ver1.deploy.prototxt',
                        bucket_name=settings.EXTRACTORS_BUCKET,
                    ),
                    weights=DataLocation(
                        storage_type='s3',
                        key='vgg16_coralnet_ver1.caffemodel',
                        bucket_name=settings.EXTRACTORS_BUCKET,
                    ),
                ),
                data_hashes=dict(
                    definition='7e0d1f6626da0dcfd00cbe62291b2c20'
                               '626eb7dacf2ba08c5eafa8a6539fad19',
                    weights='fb83781de0e207ded23bd42d7eb6e75c'
                            '1e915a6fbef74120f72732984e227cca',
                ),
            )
        case Extractors.DUMMY.value:
            return DummyExtractor()
        case _:
            assert f"{extractor_choice} isn't a supported extractor"
