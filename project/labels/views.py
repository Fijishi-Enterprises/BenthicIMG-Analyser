import re

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.urlresolvers import reverse
from django.forms import modelformset_factory
from django.http import HttpResponseRedirect
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404
from django.views.decorators.http import require_POST, require_GET

from lib.forms import get_one_formset_error, get_one_form_error
from .forms import LabelForm, LabelSetForm, LocalLabelForm, \
    BaseLocalLabelFormSet
from .models import Label, LocalLabel
from accounts.utils import get_robot_user
from annotations.models import Annotation
from images.models import Source
from lib.decorators import source_permission_required, \
    source_visibility_required, source_labelset_required
from visualization.utils import generate_patch_if_doesnt_exist, get_patch_url
from vision_backend import tasks

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
    return JsonResponse(dict(error=get_one_form_error(form)))


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
        # TODO: This doesn't seem to make the search results ordered
        # on the page
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
            
            # After changing or adding labelset, reset vision backend.
            tasks.reset_after_labelset_change(source_id)
            return HttpResponseRedirect(
                reverse('labelset_main', args=[source.id]))
        else:
            messages.error(request, get_one_form_error(labelset_form))

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
@source_labelset_required('source_id', message=(
    "This source doesn't have a labelset yet."))
def labelset_edit(request, source_id):
    """
    Edit entries of a labelset: label code, custom groups, etc.
    """
    source = get_object_or_404(Source, id=source_id)

    LocalLabelFormSet = modelformset_factory(
        LocalLabel, form=LocalLabelForm,
        formset=BaseLocalLabelFormSet, extra=0)

    if request.POST:
        formset = LocalLabelFormSet(request.POST)

        if formset.is_valid():
            formset.save()

            messages.success(request, "Label entries successfully edited.")
            return HttpResponseRedirect(
                reverse('labelset_main', args=[source.id]))
        else:
            messages.error(
                request,
                get_one_formset_error(
                    formset, lambda f: f.instance.name))
    else:
        formset = LocalLabelFormSet(
            queryset=source.labelset.get_locals_ordered_by_group_and_code())

    return render(request, 'labels/labelset_edit.html', {
        'source': source,
        'formset': formset,
    })


def label_main(request, label_id):
    """
    Main page for a particular label
    """
    label = get_object_or_404(Label, id=label_id)

    labelsets_with_label = LocalLabel.objects.filter(
        global_label_id=label_id).values_list('labelset', flat=True)
    sources_with_label = Source.objects.filter(
        labelset__in=labelsets_with_label).order_by('name')
    visible_sources_with_label = [
        s for s in sources_with_label if s.visible_to_user(request.user)]

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
