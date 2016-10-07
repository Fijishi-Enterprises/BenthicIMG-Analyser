import re

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core import serializers
from django.core.paginator import Paginator, EmptyPage, InvalidPage
from django.core.urlresolvers import reverse
from django.forms import modelformset_factory
from django.http import HttpResponseRedirect
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404
from django.template.loader import render_to_string
from django.views.decorators.http import require_POST, require_GET

from accounts.utils import get_robot_user
from annotations.models import Annotation
from images.models import Source
from lib.decorators import source_permission_required, \
    source_visibility_required, source_labelset_required
from lib.exceptions import FileProcessError
from lib.forms import get_one_formset_error, get_one_form_error
from upload.forms import CSVImportForm
from visualization.utils import generate_patch_if_doesnt_exist, get_patch_url
from vision_backend import tasks
from .forms import LabelForm, LabelSetForm, LocalLabelForm, \
    BaseLocalLabelFormSet, labels_csv_process
from .models import Label, LocalLabel, LabelSet


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
    # Replace non-letters/digits with spaces
    search_value = re.sub(r'[^A-Za-z0-9]', ' ', search_value)
    # Strip whitespace from both ends
    search_value = search_value.strip()
    # Replace multi-spaces with one space
    search_value = re.sub(r'\s{2,}', ' ', search_value)
    # Get space-separated tokens
    search_tokens = search_value.split(' ')
    # Discard blank tokens
    search_tokens = [t for t in search_tokens if t != '']

    if len(search_tokens) == 0:
        # No tokens of letters/digits. Return no results.
        return render(request, 'labels/label_box_container.html', {
            'labels': [],
        })

    # Get the labels where the name has ALL of the search tokens.
    labels = Label.objects
    for token in search_tokens:
        labels = labels.filter(name__icontains=token)

    # Sort by: verified first, highest popularity first.
    limit = 50
    sort_key = lambda x: (1 if x.verified else 0, x.popularity)
    labels = sorted(labels, key=sort_key, reverse=True)[:limit]

    return render(request, 'labels/label_box_container.html', {
        'labels': labels,
    })


@login_required
@require_GET
def labelset_search_ajax(request):
    """
    Use a text search value to get a set of labelsets.
    Return info for those labelsets.
    """
    search_value = request.GET.get('search')
    # Replace non-letters/digits with spaces
    search_value = re.sub(r'[^A-Za-z0-9]', ' ', search_value)
    # Strip whitespace from both ends
    search_value = search_value.strip()
    # Replace multi-spaces with one space
    search_value = re.sub(r'\s{2,}', ' ', search_value)
    # Get space-separated tokens
    search_tokens = search_value.split(' ')
    # Discard blank tokens
    search_tokens = [t for t in search_tokens if t != '']

    if len(search_tokens) == 0:
        # No tokens of letters/digits. Return no results.
        return render(request, 'labels/labelset_box_container.html', {
            'labelsets': [],
        })

    # Get labelsets where the source's name has ALL of the search tokens.
    sources = Source.objects
    limit = 20
    for token in search_tokens:
        sources = sources.filter(name__icontains=token)
        sources = sources.order_by('name')[:limit]
    labelset_pks = sources.values_list('labelset', flat=True)
    labelsets = LabelSet.objects.filter(pk__in=labelset_pks)

    return render(request, 'labels/labelset_box_container.html', {
        'labelsets': labelsets,
    })


@login_required
@require_GET
def labelset_labels_ajax(request, labelset_id):
    """
    Get the labels for a labelset.
    """
    labelset = get_object_or_404(LabelSet, id=labelset_id)

    return render(request, 'labels/label_box_container.html', {
        'labels': labelset.get_globals(),
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
            messages.error(request, get_one_form_error(
                labelset_form, include_field_name=False))

    else:
        labelset_form = LabelSetForm(source=source)

    initial_label_ids_str = labelset_form['label_ids'].value()
    initial_label_ids = initial_label_ids_str.split(',') \
        if initial_label_ids_str not in ['', None] else []
    initial_labels = Label.objects.filter(pk__in=initial_label_ids)

    label_ids_in_annotations = Annotation.objects.filter(source=source) \
        .values_list('label__pk', flat=True).distinct()
    label_ids_in_annotations = list(label_ids_in_annotations)

    return render(request, 'labels/labelset_add.html', {
        'source': source,
        'labelset_form': labelset_form,
        'initial_labels': initial_labels,
        'label_ids_in_annotations': label_ids_in_annotations,

        # Include a new-label form on the page. It'll be submitted to
        # another view though.
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


@source_permission_required('source_id', perm=Source.PermTypes.ADMIN.code)
def labelset_import(request, source_id):
    source = get_object_or_404(Source, id=source_id)

    csv_import_form = CSVImportForm()

    return render(request, 'labels/labelset_import.html', {
        'source': source,
        'csv_import_form': csv_import_form,
    })


@require_POST
@source_permission_required('source_id', perm=Source.PermTypes.ADMIN.code)
def labelset_import_preview_ajax(request, source_id):
    source = get_object_or_404(Source, id=source_id)

    csv_import_form = CSVImportForm(request.POST, request.FILES)
    if not csv_import_form.is_valid():
        error_message = get_one_form_error(
            csv_import_form, include_field_name=False)
        error_html = '<br>'.join(error_message.splitlines())
        return JsonResponse(dict(error=error_html))

    try:
        csv_labels = labels_csv_process(
            csv_import_form.cleaned_data['csv_file'], source)
    except FileProcessError as error:
        error_html = '<br>'.join(error.message.splitlines())
        return JsonResponse(dict(error=error_html))

    csv_labels.sort(key=lambda x: x.global_label.name)
    request.session['csv_labels'] = serializers.serialize('json', csv_labels)

    return JsonResponse(dict(
        success=True,
        previewTable=render_to_string(
            'labels/labelset_import_preview_table.html', {
                'labels': csv_labels,
            }
        ),
        previewDetail="",
    ))


@require_POST
@source_permission_required(
    'source_id', perm=Source.PermTypes.ADMIN.code, ajax=True)
def labelset_import_ajax(request, source_id):
    source = get_object_or_404(Source, id=source_id)

    csv_labels = serializers.deserialize(
        'json', request.session.pop('csv_labels'))
    if not csv_labels:
        return JsonResponse(dict(
            error=(
                "We couldn't find the expected data in your session."
                " Please try loading this page again. If the problem persists,"
                " contact a site admin."
            ),
        ))

    if not source.labelset:
        labelset = LabelSet()
        labelset.save()
        source.labelset = labelset
        source.save()

    labels_to_add = []
    for deserialized_object in csv_labels:
        label = deserialized_object.object
        if label.pk:
            # Updating an existing local label
            label.save()
        else:
            # Adding a new local label
            label.labelset = source.labelset
            labels_to_add.append(label)
    LocalLabel.objects.bulk_create(labels_to_add)

    return JsonResponse(dict(
        success=True,
    ))


def label_main(request, label_id):
    """
    Main page for a particular label
    """
    label = get_object_or_404(Label, id=label_id)

    # Sources with the label
    labelsets_with_label = LocalLabel.objects.filter(
        global_label=label).values_list('labelset', flat=True)
    all_sources_with_label = Source.objects.filter(
        labelset__in=labelsets_with_label)

    users_sources = Source.get_sources_of_user(request.user) \
        .filter(pk__in=all_sources_with_label) \
        .order_by('name')
    other_public_sources = Source.get_other_public_sources(request.user) \
        .filter(pk__in=all_sources_with_label) \
        .order_by('name')
    other_private_sources = all_sources_with_label \
        .exclude(pk__in=users_sources) \
        .exclude(pk__in=other_public_sources) \
        .order_by('name')

    # Stats
    source_count = all_sources_with_label.count()
    annotation_count = Annotation.objects.filter(label=label).count()

    return render(request, 'labels/label_main.html', {
        'label': label,
        'users_sources': users_sources,
        'other_public_sources': other_public_sources,
        'other_private_sources': other_private_sources,
        'source_count': source_count,
        'annotation_count': annotation_count,
    })


@require_GET
def label_example_patches_ajax(request, label_id):
    """
    Example patches for a label.
    """
    label = get_object_or_404(Label, id=label_id)

    all_annotations = Annotation.objects \
        .filter(label=label) \
        .exclude(user=get_robot_user()) \
        .order_by('?')

    ITEMS_PER_PAGE = 50
    try:
        page = int(request.GET.get('page', '1'))
    except ValueError:
        page = 1
    paginator = Paginator(all_annotations, ITEMS_PER_PAGE)
    try:
        page_annotations = paginator.page(page)
    except (EmptyPage, InvalidPage):
        page_annotations = paginator.page(paginator.num_pages)

    patches = []
    for index, annotation in enumerate(page_annotations.object_list):
        point = annotation.point
        image = point.image
        source = image.source

        generate_patch_if_doesnt_exist(point)

        if source.visible_to_user(request.user):
            dest_url = reverse('image_detail', args=[image.pk])
        else:
            dest_url = None

        patches.append(dict(
            source=source,
            dest_url=dest_url,
            thumbnail_url=get_patch_url(point.id),
        ))

    return JsonResponse({
        'patchesHtml': render_to_string('labels/label_example_patches.html', {
            'patches': patches,
        }),
        'isLastPage': page >= paginator.num_pages,
    })


@source_visibility_required('source_id')
def labelset_main(request, source_id):
    """
    Main page for a particular source's labelset
    """
    source = get_object_or_404(Source, id=source_id)

    if source.labelset is None:
        return render(request, 'labels/labelset_required.html', {
            'source': source,
            'message': "This source doesn't have a labelset yet.",
        })

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
