import csv

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.urlresolvers import reverse
from django.db import transaction
from django.http import HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404

from .forms import CpcPrefsForm
from .utils import create_cpc_strings, \
    create_csv_stream_response, \
    create_zipped_cpcs_stream_response, get_request_images, \
    write_annotations_csv, write_labelset_csv
from annotations.models import Annotation
from images.models import Source
from images.utils import metadata_field_names_to_labels
from lib.decorators import source_permission_required, \
    source_visibility_required
from lib.forms import get_one_form_error


@source_visibility_required('source_id')
# This is a potentially slow view that doesn't modify the database,
# so don't open a transaction for the view.
@transaction.non_atomic_requests
def export_metadata(request, source_id):
    source = get_object_or_404(Source, id=source_id)

    try:
        image_set = get_request_images(request, source)
    except ValidationError as e:
        messages.error(request, e.message)
        return HttpResponseRedirect(
            reverse('browse_images', args=[source_id]))

    response = create_csv_stream_response('metadata.csv')
    writer = csv.writer(response)

    # Get the metadata fields that we'll write CSV for.
    field_names_to_labels = metadata_field_names_to_labels(source)

    # Header row
    writer.writerow(field_names_to_labels.values())

    # Metadata, one row per image
    for image in image_set:
        row = []
        for field_name in field_names_to_labels.keys():
            # Use getattr on the Metadata model object to get the
            # metadata values. If the value is None, write ''.
            value = getattr(image.metadata, field_name)
            if value is None:
                value = ''
            row.append(value)
        writer.writerow(row)

    return response


@source_visibility_required('source_id')
@transaction.non_atomic_requests
def export_annotations_simple(request, source_id):
    source = get_object_or_404(Source, id=source_id)

    try:
        image_set = get_request_images(request, source)
    except ValidationError as e:
        messages.error(request, e.message)
        return HttpResponseRedirect(
            reverse('browse_images', args=[source_id]))

    response = create_csv_stream_response('annotations_simple.csv')
    writer = csv.writer(response)
    write_annotations_csv(writer, image_set, full=False)

    return response


@source_visibility_required('source_id')
@transaction.non_atomic_requests
def export_annotations_full(request, source_id):
    source = get_object_or_404(Source, id=source_id)

    try:
        image_set = get_request_images(request, source)
    except ValidationError as e:
        messages.error(request, e.message)
        return HttpResponseRedirect(
            reverse('browse_images', args=[source_id]))

    response = create_csv_stream_response('annotations_full.csv')
    writer = csv.writer(response)
    write_annotations_csv(writer, image_set, full=True)

    return response


@source_permission_required(
    'source_id', perm=Source.PermTypes.EDIT.code, ajax=True)
def export_annotations_cpc_create_ajax(request, source_id):
    """
    This is the first view after requesting a CPC export.
    Process the request fields, create the requested CPCs, and save them
    to the session. If there are any errors, report them with JSON.
    """
    if request.method != 'POST':
        return JsonResponse(dict(
            error="Not a POST request",
        ))

    source = get_object_or_404(Source, id=source_id)

    try:
        image_set = get_request_images(request, source)
    except ValidationError as e:
        return JsonResponse(dict(
            error=e.message
        ))

    cpc_prefs_form = CpcPrefsForm(request.POST)
    if not cpc_prefs_form.is_valid():
        return JsonResponse(dict(
            error=get_one_form_error(cpc_prefs_form),
        ))

    cpc_prefs = cpc_prefs_form.cleaned_data
    # Create a dict of filenames to CPC-file-content strings
    cpc_strings = create_cpc_strings(image_set, cpc_prefs)
    # Save CPC strings to the session
    request.session['cpc_strings'] = cpc_strings
    # Save CPC prefs to the database for use next time
    source.cpce_code_filepath = cpc_prefs['local_code_filepath']
    source.cpce_image_dir = cpc_prefs['local_image_dir']
    source.save()

    return JsonResponse(dict(
        success=True,
    ))


@source_permission_required('source_id', perm=Source.PermTypes.EDIT.code)
@transaction.non_atomic_requests
def export_annotations_cpc_serve(request, source_id):
    """
    This is the second view after requesting a CPC export.
    Grab the previously crafted CPCs from the session, and serve them in a
    zip file.
    The only reason this view really exists (instead of being merged with the
    other CPC export view) is that a file download seemingly needs to be
    non-Ajax.
    """
    cpc_strings = request.session.pop('cpc_strings', None)
    if not cpc_strings:
        messages.error(
            request,
            (
                "Export failed; we couldn't find the expected data in"
                " your session."
                " Please try the export again. If the problem persists,"
                " contact a site admin."
            ),
        )
        return HttpResponseRedirect(
            reverse('browse_images', args=[source_id]))

    response = create_zipped_cpcs_stream_response(
        cpc_strings, 'annotations_cpc.zip')

    return response


@source_visibility_required('source_id')
@transaction.non_atomic_requests
def export_image_covers(request, source_id):
    source = get_object_or_404(Source, id=source_id)

    try:
        image_set = get_request_images(request, source)
    except ValidationError as e:
        messages.error(request, e.message)
        return HttpResponseRedirect(
            reverse('browse_images', args=[source_id]))

    response = create_csv_stream_response('percent_covers.csv')
    writer = csv.writer(response)

    local_labels = source.labelset.get_locals_ordered_by_group_and_code()

    # Header row
    row = ["Name", "Annotation status", "Annotation area"]
    row.extend(local_labels.values_list('code', flat=True))
    writer.writerow(row)

    # One row per image
    for image in image_set:
        row = [
            image.metadata.name,
            image.get_annotation_status_str(),
            image.annotation_area_display(),
        ]

        image_annotations = Annotation.objects.filter(image=image)
        image_annotation_count = image_annotations.count()
        for local_label in local_labels:
            if image_annotation_count == 0:
                coverage_fraction = 0
            else:
                global_label = local_label.global_label
                coverage_fraction = (
                    image_annotations.filter(label=global_label).count()
                    / float(image_annotation_count)
                )
            coverage_percent_str = format(coverage_fraction * 100.0, '.3f')
            row.append(coverage_percent_str)
        writer.writerow(row)

    return response


@source_visibility_required('source_id')
@transaction.non_atomic_requests
def export_labelset(request, source_id):
    source = get_object_or_404(Source, id=source_id)

    response = create_csv_stream_response('labelset.csv')
    writer = csv.writer(response)
    write_labelset_csv(writer, source)

    return response
