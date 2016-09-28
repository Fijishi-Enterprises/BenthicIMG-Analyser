import numpy as np

from django.conf import settings

from lib.utils import direct_s3_read, direct_s3_write
from images.models import Source, Point
from labels.models import LabelSet, Label, LabelGroup

from .models import Classifier, Score





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


def get_current_confusion_matrix(source_id):
    """
    Returns the confusion matrix for the latest classifier in source_id. 
    """

    source = Source.objects.get(id = source_id)
    latestRobot = source.get_latest_robot()
    if latestRobot == None:
        return None
    (cm, labelIds) = get_confusion_matrix(latestRobot)
    return (cm, labelIds)

def get_confusion_matrix(classifier):
    """
    Returns confusion matrix for classifier object.
    """
    
    valres = direct_s3_read(settings.ROBOT_MODEL_VALRESULT_PATTERN.format(pk = classifier.pk, media = settings.AWS_LOCATION), 'json')

    classes = [l.global_label_id for l in LabelSet.objects.get(source = classifier.source).get_labels()]

    cm = np.zeros((len(classes), len(classes)), dtype = int)

    for gt, est in zip(valres['gt'], valres['est']):
        cm[gt, est] = cm[gt, est] + 1
    
    return (cm, classes)

def collapse_confusion_matrix(cm, labelIds):
    """
    (cm_func, fdict, funcIds) = collapse_confusion_matrix(cm, labelIds)
    OUTPUT cm_func. a numpy matrix of functional group confusion matrix
    OUTPUT fdict a dictionary that maps the functional group id to the row (and column) number in the confusion matrix
    OUTPUT funcIds is a list that maps the row (or column) to the functional group id. ("inverse" or the fdict).
    """

    nlabels = len(labelIds)

    # create a labelmap that maps the labels to functional groups. 
    # The thing is that we can't rely on the functional group id field, 
    # since this may not start on one, nor be consecutive.
    funcgroups = LabelGroup.objects.filter().order_by('id') # get all groups
    nfuncgroups = len(funcgroups)
    fdict = {} # this will map group_id to a counter from 0 to (number of functional groups - 1).
    for itt, group in enumerate(funcgroups):
        fdict[group.id] = itt

    # create the 'inverse' of the dictionary, namely a list of the functional groups. Same as the labelIds list but for functional groups. This is not used in this file, but is useful for other situations
    funcIds = []    
    for itt, group in enumerate(funcgroups):
        funcIds.append(int(group.id))

    # create a map from labelid to the functional group consecutive id. Needed for the matrix collapse.
    funcMap = np.zeros( (nlabels, 1), dtype = int )
    for labelItt in range(nlabels):
        funcMap[labelItt] = fdict[Label.objects.get(id=labelIds[labelItt]).group_id]

    ## collapse columns
    
    # create an intermediate confusion matrix to facilitate the collapse
    cm_int = np.zeros( ( nlabels, nfuncgroups ), dtype = int )
        
    # do the collapse
    for rowlabelitt in range(nlabels):
        for collabelitt in range(nlabels):
            cm_int[rowlabelitt, funcMap[collabelitt]] += cm[rowlabelitt, collabelitt]
    
    ## collapse rows
    # create the final confusion matrix for functional groups
    cm_func = np.zeros( ( nfuncgroups, nfuncgroups ), dtype = int )
        
    # do the collapse
    for rowlabelitt in range(nlabels):
        for funclabelitt in range(nfuncgroups):
            cm_func[funcMap[rowlabelitt], funclabelitt] += cm_int[rowlabelitt, funclabelitt]

    return (cm_func, fdict, funcIds)


def confusion_matrix_normalize(cm):
    """
    (cm, row_sums) = confusion_matrix_normalize(cm)
    OUTPUT cm is row-normalized confusion matrix. Exception. if row sums to zero, it will not be normalized.
    OUTPUT row_sums is the row sums of the input cm
    """
    row_sums = cm.sum(axis=1)
    cm = np.float32(cm)
    row_sums[row_sums == 0] = 1
    cm_normalized = cm / row_sums[:, np.newaxis]

    return (cm_normalized, row_sums)


def format_cm_for_display(cm, row_sums, labelobjects, labelIds):
    """
    This function takes a cm, and labels, and formats it for display on screen. 
    OUTPUT cm_str is a list of strings.
    """

    nlabels = len(labelIds)
    cm_str = ['']
    for thisid in labelIds:
        cm_str.append(str(labelobjects.get(id = thisid).name))
    cm_str.append('Count')
    for row in range(nlabels):
        cm_str.append(str(labelobjects.get(id = labelIds[row]).name)) #the first entry is the name of the funcgroup.
        for col in range(nlabels):
            cm_str.append("%.2f" % cm[row][col])
        cm_str.append("%.0f" % row_sums[row]) # add the count for this row

    return cm_str


def accuracy_from_cm(cm):
    """
    Calculates accuracy and kappa from confusion matrix.
    """
    cm = np.float32(cm)
    acc = np.sum(np.diagonal(cm))/np.sum(cm)

    pgt = cm.sum(axis=1) / np.sum(cm) #probability of the ground truth to predict each class

    pest = cm.sum(axis=0) / np.sum(cm) #probability of the estimates to predict each class

    pe = np.sum(pgt * pest) #probaility of randomly guessing the same thing!

    if (pe == 1):
        cok = 1
    else:
        cok = (acc - pe) / (1 - pe) #cohens kappa!

    return (acc, cok)


def get_alleviate_meta(robot):
    """
    TODO: write this function for the new vision system!
    """
    
    if True:
        ok = 0
    else:
        f = open(alleviate_meta_file)
        meta=json.loads(f.read())
        f.close()
        ok = meta['ok']

    if (ok == 1):
        alleviate_meta = dict(        
            suggestion = meta['keepRatio'],
            score_translate = meta['thout'],
            plot_path = os.path.join(ALLEVIATE_IMAGE_DIR, str(robot.version) + '.png'),
            plot_url = os.path.join(ALLEVIATE_IMAGE_URL, str(robot.version) + '.png'),
            ok = True,
        )
    else:
        alleviate_meta = dict(        
            ok = False,
        )
    return (alleviate_meta)
