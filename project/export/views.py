import csv

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.urlresolvers import reverse
from django.db import transaction
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404

from annotations.models import Annotation
from .utils import create_csv_stream_response, get_request_images, \
    write_annotations_csv
from images.models import Source
from images.utils import metadata_field_names_to_labels
from lib.decorators import source_visibility_required


@source_visibility_required('source_id')
# This is a potentially slow view that doesn't modify the database,
# so don't open a transaction for the view.
@transaction.non_atomic_requests
def export_metadata(request, source_id):
    source = get_object_or_404(Source, id=source_id)

    try:
        image_set = get_request_images(request, source)
    except ValidationError:
        messages.error(request, "Search parameters were invalid.")
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
    except ValidationError:
        messages.error(request, "Search parameters were invalid.")
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
    except ValidationError:
        messages.error(request, "Search parameters were invalid.")
        return HttpResponseRedirect(
            reverse('browse_images', args=[source_id]))

    response = create_csv_stream_response('annotations_full.csv')
    writer = csv.writer(response)
    write_annotations_csv(writer, image_set, full=True)

    return response


@source_visibility_required('source_id')
@transaction.non_atomic_requests
def export_image_covers(request, source_id):
    source = get_object_or_404(Source, id=source_id)

    try:
        image_set = get_request_images(request, source)
    except ValidationError:
        messages.error(request, "Search parameters were invalid.")
        return HttpResponseRedirect(
            reverse('browse_images', args=[source_id]))

    response = create_csv_stream_response('annotations_full.csv')
    writer = csv.writer(response)

    labels = source.labelset.labels.all().order_by('group', 'code')

    # Header row
    row = ["Name", "Annotation status", "Annotation area"]
    row.extend(labels.values_list('code', flat=True))
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
        for label in labels:
            if image_annotation_count == 0:
                coverage_fraction = 0
            else:
                coverage_fraction = (
                    image_annotations.filter(label=label).count()
                    / float(image_annotation_count)
                )
            coverage_percent_str = format(coverage_fraction * 100.0, '.1f')
            row.append(coverage_percent_str)
        writer.writerow(row)

    return response