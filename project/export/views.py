import csv

from django.contrib import messages
from django.core.urlresolvers import reverse
from django.http import HttpResponse
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404

from images.models import Source, Image
from images.utils import metadata_field_names_to_labels
from lib.decorators import source_visibility_required
from visualization.forms import process_image_forms


@source_visibility_required('source_id')
def export_metadata(request, source_id):
    """
    From the browse images page, select delete from the action form.
    """
    source = get_object_or_404(Source, id=source_id)

    image_form = \
        process_image_forms(request.POST, source, has_annotation_status=True)
    if image_form:
        if image_form.is_valid():
            image_set = image_form.get_images()
        else:
            # This is an unusual error case where the current image search
            # worked for the Browse-images page load, but not for the
            # subsequent export.
            # Nothing fancy here, we'll just redirect back to Browse and
            # display a top-of-page message.
            messages.error(request, "Search parameters were invalid.")
            return HttpResponseRedirect(
                reverse('browse_images', args=[source_id]))
    else:
        image_set = Image.objects.filter(source=source)

    image_set = image_set.order_by('metadata__name')

    # Get the metadata fields that we'll write CSV for.
    field_names_to_labels = metadata_field_names_to_labels(source)

    # Create a downloadable-file response.
    # https://docs.djangoproject.com/en/dev/ref/request-response/#telling-the-browser-to-treat-the-response-as-a-file-attachment
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment;filename="metadata.csv"'
    # The response can be used as a stream, which a CSV writer can write to.
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