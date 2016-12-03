import json
import datetime
import csv

import numpy as np

from django.contrib.auth.decorators import permission_required
from django.shortcuts import render
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect, HttpResponse
from django.contrib.auth.decorators import permission_required

from lib.decorators import source_visibility_required

from images.models import Source, Image
from images.utils import source_robot_status
from labels.models import LocalLabel, Label

from .forms import TreshForm
from .confmatrix import ConfMatrix
from .utils import labelset_mapper, map_labels, get_total_messages_in_jobs_queue, get_alleviate
from .models import Classifier


@permission_required('is_superuser')
def backend_overview(request):

    nimgs = Image.objects.filter().count()
    nconfirmed = Image.objects.filter(confirmed = True).count()
    nclassified = Image.objects.filter(features__classified = True).count()
    nextracted = Image.objects.filter(features__extracted = True).count()
    nnaked = Image.objects.filter(features__extracted = False, confirmed = False).count()

    img_stats = {
        'nimgs': nimgs,
        'nconfirmed': nconfirmed,
        'nclassified': nclassified, 
        'nextracted': nextracted,
        'nnaked': nnaked,
        'fextracted': '{:.1f}'.format(100*float(nextracted) / nimgs),
        'fconfirmed': '{:.1f}'.format(100*float(nconfirmed) / nimgs),
        'fclassified': '{:.1f}'.format(100*float(nclassified) / nimgs),
        'fnaked': '{:.1f}'.format(100*float(nnaked) / nimgs)
    }

    clf_stats = {
        'nclassifiers': Classifier.objects.filter().count(),
        'nvalidclassifiers': Classifier.objects.filter(valid=True).count(),
        'nsources': Source.objects.filter().count(),
        'valid_ratio': '{:.1f}'.format(float(Classifier.objects.filter(valid=True).count()) / Source.objects.filter().count())
    }

    laundry_list = []
    for source in Source.objects.filter().order_by('-id'):
        laundry_list.append(source_robot_status(source.id))

    laundry_list = sorted(laundry_list, key=lambda k: (-k['need_attention'], -k['id']))
    
    return render(request, 'vision_backend/overview.html', {
        'laundry_list': laundry_list,
        'img_stats': img_stats,
        'clf_stats': clf_stats,
        'spacer_queue': get_total_messages_in_jobs_queue(),
    })


@source_visibility_required('source_id')
def backend_main(request, source_id):
    
    # Read plotting input from the request. (Using GET is OK here as this view only reads from DB).
    confidence_threshold = int(request.GET.get('confidence_threshold', 0))
    labelmode = request.GET.get('labelmode', 'full')
    
    # Initialize form
    form = TreshForm()    
    form.initial['confidence_threshold'] = confidence_threshold
    form.initial['labelmode'] = labelmode

    # Mapper for pretty priting.
    labelmodestr = {
        'full': 'full labelset',
        'func': 'functional groups',
    }

    # Get source
    source = Source.objects.get(id = source_id)
    
    # Make sure that there is a classifier for this source.
    if not source.has_robot():
        return render(request, 'vision_backend/backend_main.html', {
        'form': form,
        'has_classifier': False,
        'source': source,
    })
    
    cc = source.get_latest_robot()
    if 'valres' in request.session.keys() and 'ccpk' in request.session.keys() and request.session['ccpk'] == cc.pk:
        pass
    else:
        valres = source.get_latest_robot().valres
        request.session['valres'] = valres
        request.session['ccpk'] = cc.pk
    
    # Load stored variables to local namsspace
    valres = request.session['valres']
    
    # find classmap and class names for selected labelmode
    classmap, classnames = labelset_mapper(labelmode, valres['classes'], source)

    # Initialize confusion matrix
    cm = ConfMatrix(len(classnames), labelset = classnames)

    # Add datapoints above the threhold.
    cm.add_select(map_labels(valres['gt'], classmap), map_labels(valres['est'], classmap), valres['scores'], confidence_threshold / 100.0)

    # Sort by descending order.
    cm.sort()
    
    # Export for heatmap
    cm_render = dict()
    cm_render['data_'], cm_render['xlabels'], cm_render['ylabels'] = cm.render_for_heatmap()
    cm_render['title_'] = json.dumps('Confusion matrix for {} (acc:{}, n: {})'.format(labelmodestr[labelmode], round(100*cm.get_accuracy()[0], 1), int(np.sum(np.sum(cm.cm)))))
    cm_render['css_height'] = max(500, len(classnames) * 20 + 280)
    cm_render['css_width'] = max(600, len(classnames) * 20 + 300)
    
    
    # Prepare the alleviate plot if not allready in session
    if not 'alleviate_data' in request.session.keys():
        acc_full, ratios, confs = get_alleviate(valres['gt'], valres['est'], valres['scores'])
        classmap, _ = labelset_mapper('func', valres['classes'], source)
        acc_func, _, _ = get_alleviate(map_labels(valres['gt'], classmap), map_labels(valres['est'], classmap), valres['scores'])
        request.session['alleviate'] = dict()
        for member in ['acc_full', 'acc_func', 'ratios']:
            request.session['alleviate'][member] = [[conf, val] for val, conf in zip(eval(member), confs)]

    # Handle the case where we are exporting the confusion matrix.
    if request.method == 'POST' and request.POST.get('export_cm', None):
        vecfmt = np.vectorize(myfmt)
        
        #create csv file
        response = HttpResponse()
        response['Content-Disposition'] = 'attachment;filename=confusion_matrix_{}_{}.csv'.format(labelmode, confidence_threshold)
        writer = csv.writer(response)
        
        for enu, classname in enumerate(classnames):
            row = []
            row.append(classname)
            row.extend(vecfmt(cm.cm[enu, :]))
            writer.writerow(row)

        return response

    return render(request, 'vision_backend/backend_main.html', {
        'form': form,
        'has_classifier': True,
        'source': source,
        'cm': cm_render,
        'alleviate': request.session['alleviate'],
    })

# helper function to format numpy outputs
def myfmt(r):
    return "%.0f" % (r,)

@source_visibility_required('source_id')
def download_cm(request, source_id, namestr):
    vecfmt = vectorize(myfmt)
    (fullcm, labelIds) = get_confusion_matrix(Robot.objects.get(version = robot_version))
    if namestr == "full":
        cm = fullcm
        labelObjects = Label.objects.filter()
    else:
        (cm, placeholder, labelIds) = collapse_confusion_matrix(fullcm, labelIds)
        labelObjects = LabelGroup.objects.filter()

    #creating csv file
    response = HttpResponse(type='text/csv')
    response['Content-Disposition'] = 'attachment;filename=confusion_matrix.csv'
    writer = csv.writer(response)
    
    ngroups = len(labelIds)
    for i in range(ngroups):
        row = []
        row.append(labelObjects.get(id=labelIds[i]).name)
        row.extend(vecfmt(cm[i, :]))
        writer.writerow(row)

    return response
