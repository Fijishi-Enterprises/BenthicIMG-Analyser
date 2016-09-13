import json
import re

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404
from django.views.decorators.http import require_POST, require_GET

from .forms import LabelForm, LabelSetForm
from .models import Label
from accounts.utils import get_robot_user
from annotations.models import Annotation
from images.models import Source
from lib.decorators import source_permission_required, \
    source_visibility_required
from visualization.utils import generate_patch_if_doesnt_exist, get_patch_url


@login_required
@require_POST
def label_new_ajax(request):
    """
    Create a new global label (through Ajax).
    """
    form = LabelForm(request.POST, request.FILES)

    # is_valid() checks for label conflicts in the database
    # (same-name label found, etc.).
    if form.is_valid():
        label = form.instance
        label.created_by = request.user
        label.save()
        return render(request, 'labels/label_box_container.html', {
            'labels': [label],
        })

    # Not valid. Find the first error and return it.
    for field_name, error_messages in form.errors.iteritems():
        if error_messages:
            message = "Error for {label}: {error}".format(
                label=form[field_name].label, error=error_messages[0])
            return JsonResponse(dict(error=message))

    return JsonResponse(dict(error=(
        "Unknown error. If the problem persists, please contact the admins.")))


@login_required
@require_GET
def label_search_ajax(request):
    """
    Use a text search value to get a set of global labels.
    Return general info for those global labels.
    """
    search_value = request.GET.get('search')
    # Strip whitespace from both ends
    search_value = search_value.strip()
    # Replace non-letters/digits with spaces
    search_value = re.sub(r'[^A-Za-z0-9]', ' ', search_value)
    # Replace multi-spaces with one space
    search_value = re.sub(r'\s{2,}', ' ', search_value)
    # Get space-separated tokens
    search_tokens = search_value.split(' ')

    # Get the labels where the name has ALL of the search tokens.
    labels = Label.objects
    for token in search_tokens:
        labels = labels.filter(name__icontains=token)
        labels.order_by('name')

    return render(request, 'labels/label_box_container.html', {
        'labels': labels,
    })


@source_permission_required('source_id', perm=Source.PermTypes.ADMIN.code)
def labelset_add(request, source_id):
    """
    Add or remove label entries from a labelset
    (or pick entries for a new labelset).
    """
    source = get_object_or_404(Source, id=source_id)

    if request.method == 'POST':

        labelset_form = LabelSetForm(request.POST, source=source)

        if labelset_form.is_valid():
            labelset_was_created = labelset_form.save_labelset()
            if labelset_was_created:
                messages.success(request, "Labelset successfully created.")
            else:
                messages.success(request, "Labelset successfully changed.")

            return HttpResponseRedirect(
                reverse('labelset_main', args=[source.id]))
        else:
            messages.error(request, labelset_form.get_error())

    else:
        labelset_form = LabelSetForm(source=source)

    label_ids_in_annotations = Annotation.objects.filter(source=source) \
        .values_list('label__pk', flat=True).distinct()
    label_ids_in_annotations = list(label_ids_in_annotations)

    return render(request, 'labels/labelset_add.html', {
        'source': source,
        'labelset_form': labelset_form,
        'label_ids_in_annotations': label_ids_in_annotations,

        # Include this form on the page, but it'll be processed in a
        # different view
        'new_label_form': LabelForm(),
    })


@source_permission_required('source_id', perm=Source.PermTypes.ADMIN.code)
def labelset_edit_entries(request, source_id):
    """
    Page to edit a source's labelset.
    """

    source = get_object_or_404(Source, id=source_id)

    if source.labelset is None:
        return HttpResponseRedirect(reverse('labelset_add', args=[source.id]))

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
        return HttpResponseRedirect(reverse('labelset_add', args=[source.id]))

    return render(request, 'labels/labelset_main.html', {
        'source': source,
        'labelset': source.labelset,
        'labels': source.labelset.get_locals_ordered_by_group_and_code(),
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
