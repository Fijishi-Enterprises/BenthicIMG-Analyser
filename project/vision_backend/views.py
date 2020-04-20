from __future__ import division
import json
from backports import csv

import numpy as np

from django.shortcuts import render
from django.http import  HttpResponse
from django.contrib.auth.decorators import permission_required
from celery.task.control import inspect

from lib.decorators import source_visibility_required

from images.models import Source, Image
from images.utils import source_robot_status

from .forms import TreshForm, CmTestForm
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
        'fextracted': '{:.1f}'.format(100*nextracted / nimgs),
        'fconfirmed': '{:.1f}'.format(100*nconfirmed / nimgs),
        'fclassified': '{:.1f}'.format(100*nclassified / nimgs),
        'fnaked': '{:.1f}'.format(100*nnaked / nimgs)
    }

    clf_stats = {
        'nclassifiers': Classifier.objects.filter().count(),
        'nvalidclassifiers': Classifier.objects.filter(valid=True).count(),
        'nsources': Source.objects.filter().count(),
        'valid_ratio': '{:.1f}'.format(Classifier.objects.filter(valid=True).count() / Source.objects.filter().count())
    }

    def first_queue_length(inspect_category):
        # For a given inspect category, there should be only one queue (e.g.
        # 'celery@Ubuntu'). This function gets the length of that queue.
        first_queue = next(iter(inspect_category.values()))
        return len(first_queue)

    i = inspect()
    isch = i.scheduled()
    iact = i.active()
    iqu = i.reserved()
    q_stats = {
        'spacer': get_total_messages_in_jobs_queue(),
        'celery_scheduled': first_queue_length(isch),
        'celery_active': first_queue_length(iact),
        'celery_queued': first_queue_length(iqu),
    }

    laundry_list = []
    for source in Source.objects.filter().order_by('-id'):
        laundry_list.append(source_robot_status(source.id))

    laundry_list = sorted(laundry_list, key=lambda k: (-k['need_attention'], -k['id']))
    
    return render(request, 'vision_backend/overview.html', {
        'laundry_list': laundry_list,
        'img_stats': img_stats,
        'clf_stats': clf_stats,
        'q_stats':q_stats
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
    cm.add_select(map_labels(valres['gt'], classmap), map_labels(valres['est'], classmap), valres['scores'], confidence_threshold / 100)

    # Sort by descending order.
    cm.sort()

    max_display_labels = 50
    
    if cm.nclasses > max_display_labels:
        cm.cut(max_display_labels)
    
    # Export for heatmap
    cm_render = dict()
    cm_render['data_'], cm_render['xlabels'], cm_render['ylabels'] = cm.render_for_heatmap()
    cm_render['title_'] = json.dumps('Confusion matrix for {} (acc:{}, n: {})'.format(labelmodestr[labelmode], round(100*cm.get_accuracy()[0], 1), int(np.sum(np.sum(cm.cm)))))
    cm_render['css_height'] = max(500, cm.nclasses * 22 + 320)
    cm_render['css_width'] = max(600, cm.nclasses * 22 + 360)
    
    
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
        
        for enu, classname in enumerate(cm.labelset):
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


@permission_required('is_superuser')
def cm_test(request):
    """
    Test and debug function for confusion matrices.
    """
    nlabels = int(request.GET.get('nlabels', 5))
    namelength = int(request.GET.get('namelength', 25))
    
    # Initialize form
    form = CmTestForm()    
    form.initial['nlabels'] = nlabels
    form.initial['namelength'] = namelength
    
    # Initialize confusion matrix
    cm = ConfMatrix(nlabels, labelset = ['a'*namelength]*nlabels)

    # Add datapoints above the threhold.
    cm.add(np.random.choice(nlabels, size = 10*nlabels), np.random.choice(nlabels, size = 10*nlabels))

    # Sort by descending order.
    cm.sort()

    max_display_labels = 50
    
    if nlabels > max_display_labels:
        cm.cut(max_display_labels)
    # Export for heatmap
    cm_render = dict()
    cm_render['data_'], cm_render['xlabels'], cm_render['ylabels'] = cm.render_for_heatmap()
    cm_render['title_'] = '"This is a title"'
    cm_render['css_height'] = max(500, cm.nclasses * 22 + 320)
    cm_render['css_width'] = max(600, cm.nclasses * 22 + 360)
    

    return render(request, 'vision_backend/cm_test.html', {
        'form': form,
        'cm': cm_render,
    })

