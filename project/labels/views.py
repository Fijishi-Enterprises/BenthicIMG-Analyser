import json
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect
from django.shortcuts import render, get_object_or_404

from .forms import NewLabelForm, NewLabelSetForm
from .models import Label
from accounts.utils import get_robot_user
from annotations.models import Annotation
from images.models import Source
from lib.decorators import source_permission_required, \
    source_visibility_required
from visualization.utils import generate_patch_if_doesnt_exist, get_patch_url


@login_required
def label_new(request):
    """
    Page to create a new label for CoralNet.
    NOTE: This view might be obsolete, deferring in favor of
    having the new-label form only be in the create-labelset page.
    """
    if request.method == 'POST':
        form = NewLabelForm(request.POST)

        if form.is_valid():
            label = form.save()
            messages.success(request, 'Label successfully created.')
            return HttpResponseRedirect(reverse('label_main', args=[label.id]))
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = NewLabelForm()

    return render(request, 'labels/label_new.html', {
        'form': form,
    })


@source_permission_required('source_id', perm=Source.PermTypes.ADMIN.code)
def labelset_new(request, source_id):
    """
    Page to create a labelset for a source.
    """

    source = get_object_or_404(Source, id=source_id)
    showLabelForm = False
    initiallyCheckedLabels = []

    if request.method == 'POST':

        initiallyCheckedLabels = [int(labelId) for labelId in request.POST.getlist('labels')]

        if 'create_label' in request.POST:
            labelForm = NewLabelForm(request.POST, request.FILES)
            newLabel = None

            # is_valid() checks for label conflicts in the database (same-name label found, etc.).
            if labelForm.is_valid():
                newLabel = labelForm.instance
                newLabel.created_by = request.user
                newLabel.save()
                messages.success(request, 'Label successfully created.')
            else:
                messages.error(request, 'Please correct the errors below.')
                showLabelForm = True

            # The labelset form should now have the new label.
            labelSetForm = NewLabelSetForm()

            # If a label was added, the user probably wanted to add it to their
            # labelset, so pre-check that label.
            if newLabel:
                initiallyCheckedLabels.append(newLabel.id)

        else:  # 'create_labelset' in request.POST
            labelSetForm = NewLabelSetForm(request.POST)
            labelForm = NewLabelForm()

            if labelSetForm.is_valid():
                labelset = labelSetForm.save()
                source.labelset = labelset
                source.save()

                messages.success(request, 'LabelSet successfully created.')
                return HttpResponseRedirect \
                    (reverse('labelset_main', args=[source.id]))
            else:
                messages.error(request, 'Please correct the errors below.')

    else:
        labelForm = NewLabelForm()
        labelSetForm = NewLabelSetForm()

    allLabels = [dict(labelId=str(id), name=label.name,
                      code=label.code, group=label.group.name)
                 for id, label in labelSetForm['labels'].field.choices]

    # Dict that tells whether a label should be initially checked: {85: True, 86: True, ...}.
    isInitiallyChecked = dict()
    for labelId, label in labelSetForm['labels'].field.choices:
        isInitiallyChecked[labelId] = labelId in initiallyCheckedLabels

    return render(request, 'labels/labelset_new.html', {
        'showLabelFormInitially': json.dumps(showLabelForm),    # Convert Python bool to JSON bool
        'labelSetForm': labelSetForm,
        'labelForm': labelForm,
        'source': source,
        'isEditLabelsetForm': False,

        'allLabels': allLabels,    # label dictionary, for accessing as a template variable
        'allLabelsJSON': json.dumps(allLabels),    # label dictionary, for JS
        'isInitiallyChecked': json.dumps(isInitiallyChecked),
    })


@source_permission_required('source_id', perm=Source.PermTypes.ADMIN.code)
def labelset_edit(request, source_id):
    """
    Page to edit a source's labelset.
    """

    source = get_object_or_404(Source, id=source_id)

    if source.labelset is None:
        return HttpResponseRedirect(reverse('labelset_new', args=[source.id]))

    labelset = source.labelset
    showLabelForm = False
    labelsInLabelset = [label.id for label in labelset.labels.all()]
    initiallyCheckedLabels = labelsInLabelset

    if request.method == 'POST':

        initiallyCheckedLabels = [int(labelId) for labelId in request.POST.getlist('labels')]

        if 'create_label' in request.POST:
            labelForm = NewLabelForm(request.POST, request.FILES)
            newLabel = None

            # is_valid() checks for label conflicts in the database (same-name label found, etc.).
            if labelForm.is_valid():
                newLabel = labelForm.instance
                newLabel.created_by = request.user
                newLabel.save()
                messages.success(request, 'Label successfully created.')
            else:
                messages.error(request, 'Please correct the errors below.')
                showLabelForm = True

            # The labelset form should now have the new label.
            labelSetForm = NewLabelSetForm()

            # If a label was added, the user probably wanted to add it to their
            # labelset, so pre-check that label.
            if newLabel:
                initiallyCheckedLabels.append(newLabel.id)

        elif 'edit_labelset' in request.POST:
            labelSetForm = NewLabelSetForm(request.POST, instance=labelset)
            labelForm = NewLabelForm()

            if labelSetForm.is_valid():
                labelSetForm.save()

                messages.success(request, 'LabelSet successfully edited.')
                return HttpResponseRedirect \
                    (reverse('labelset_main', args=[source.id]))
            else:
                messages.error(request, 'Please correct the errors below.')

        else: # Cancel
            messages.success(request, 'Edit cancelled.')
            return HttpResponseRedirect \
                (reverse('labelset_main', args=[source_id]))

    else:
        labelForm = NewLabelForm()
        labelSetForm = NewLabelSetForm(instance=labelset)

    # Dictionary of info for each label in the labelset form.
    allLabels = [dict(labelId=str(id), name=label.name,
                      code=label.code, group=label.group.name)
                 for id, label in labelSetForm['labels'].field.choices]

    # Dict that tells whether a label is already in the labelset: {85: True, 86: True, ...}.
    # This is basically a workaround around JavaScript's lack of a widely supported "is element in list" function.
    isInLabelset = dict()
    for labelId, label in labelSetForm['labels'].field.choices:
        isInLabelset[labelId] = labelId in labelsInLabelset

    # Dict that tells whether a label should be initially checked: {85: True, 86: True, ...}.
    isInitiallyChecked = dict()
    for labelId, label in labelSetForm['labels'].field.choices:
        isInitiallyChecked[labelId] = labelId in initiallyCheckedLabels

    # Dict that tells whether an initially-checked label's status is changeable: {85: True, 86: False, ...}.
    # A label is unchangeable if it's being used by any annotations in this source.
    isLabelUnchangeable = dict()
    for labelId, label in labelSetForm['labels'].field.choices:
        if labelId in initiallyCheckedLabels:
            annotationsForLabel = Annotation.objects.filter \
                (image__source=source, label__id=labelId)
            isLabelUnchangeable[labelId] = len(annotationsForLabel) > 0
        else:
            isLabelUnchangeable[labelId] = False


    return render(request, 'labels/labelset_edit.html', {
        'showLabelFormInitially': json.dumps(showLabelForm),    # Python bool to JSON bool
        'labelSetForm': labelSetForm,
        'labelForm': labelForm,
        'source': source,
        'isEditLabelsetForm': True,

        'allLabels': allLabels,    # label dictionary, for accessing as a template variable
        'allLabelsJSON': json.dumps(allLabels),    # label dictionary, for JS
        'isInLabelset': json.dumps(isInLabelset),
        'isInitiallyChecked': json.dumps(isInitiallyChecked),
        'isLabelUnchangeable': json.dumps(isLabelUnchangeable),
    })


def label_main(request, label_id):
    """
    Main page for a particular label
    """

    label = get_object_or_404(Label, id=label_id)

    sources_with_label = Source.objects.filter(labelset__labels=label).order_by \
        ('name')
    visible_sources_with_label = [s for s in sources_with_label if s.visible_to_user(request.user)]

    # Differentiate between the sources that the user is part of
    # and the other public sources.  Sort the source list accordingly, too.
    sources_of_user = Source.get_sources_of_user(request.user)

    source_types = []
    for s in visible_sources_with_label:
        if s in sources_of_user:
            source_types.append('mine')
        else:
            source_types.append('public')

    visible_sources_with_label = zip(source_types, visible_sources_with_label)
    visible_sources_with_label.sort \
        (key=lambda x: x[0])  # Mine first, then public

    # Example patches.
    example_annotations = Annotation.objects \
        .filter(label=label, image__source__visibility=Source.VisibilityTypes.PUBLIC) \
        .exclude(user=get_robot_user()) \
        .order_by('?')[:5]

    for anno in example_annotations:
        generate_patch_if_doesnt_exist(anno.point)

    patches = [
        dict(
            annotation=a,
            fullImage=a.image,
            source=a.image.source,
            url=get_patch_url(a.point.pk),
            row=a.point.row,
            col=a.point.column,
            pointNum=a.point.point_number,
        )
        for a in example_annotations
        ]

    return render(request, 'labels/label_main.html', {
        'label': label,
        'visible_sources_with_label': visible_sources_with_label,
        'patches': patches,
    })


@source_visibility_required('source_id')
def labelset_main(request, source_id):
    """
    Main page for a particular source's labelset
    """

    source = get_object_or_404(Source, id=source_id)

    if source.labelset is None:
        return HttpResponseRedirect(reverse('labelset_new', args=[source.id]))

    labelset = source.labelset
    labels = labelset.labels.all().order_by('group__id', 'name')


    return render(request, 'labels/labelset_main.html', {
        'source': source,
        'labelset': labelset,
        'labels': labels,
    })


def labelset_list(request):
    """
    Page with a list of all the labelsets

    Not sure where to put a link to this page. It's a little less
    useful when each source has its own labelset, but this view still
    might be useful if someone wants to browse through labelsets that
    they could base their labelset off of.
    """

    publicSources = Source.objects.filter \
        (visibility=Source.VisibilityTypes.PUBLIC)
    publicSourcesWithLabelsets = publicSources.exclude(labelset=None)

    return render(request, 'labels/labelset_list.html', {
        'publicSourcesWithLabelsets': publicSourcesWithLabelsets,
    })


def label_list(request):
    """
    Page with a list of all the labels
    """

    labels = Label.objects.all().order_by('group__id', 'name')

    return render(request, 'labels/label_list.html', {
        'labels': labels,
    })
