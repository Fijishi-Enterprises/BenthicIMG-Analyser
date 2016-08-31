import csv

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404

from .utils import create_csv_stream_response, get_request_images, \
    write_annotations_csv
from images.models import Source
from images.utils import metadata_field_names_to_labels
from lib.decorators import source_visibility_required


@source_visibility_required('source_id')
def export_metadata(request, source_id):
    source = get_object_or_404(Source, id=source_id)

    try:
        image_set = get_request_images(request, source)
    except ValidationError:
        messages.error(request, "Search parameters were invalid.")
        return HttpResponseRedirect(
            reverse('browse_images', args=[source_id]))

    # Get the metadata fields that we'll write CSV for.
    field_names_to_labels = metadata_field_names_to_labels(source)

    response = create_csv_stream_response('metadata.csv')
    writer = csv.writer(response)

    # Header row
    writer.writerow(field_names_to_labels.values())

    # Metadata, one row per image
    for image in image_set:
        row_data = []
        for field_name in field_names_to_labels.keys():
            # Use getattr on the Metadata model object to get the
            # metadata values. If the value is None, write ''.
            value = getattr(image.metadata, field_name)
            if value is None:
                value = ''
            row_data.append(value)
        writer.writerow(row_data)

    return response


@source_visibility_required('source_id')
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