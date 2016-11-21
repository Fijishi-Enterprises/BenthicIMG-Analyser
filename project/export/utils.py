from django.core.exceptions import ValidationError
from django.http import HttpResponse

from annotations.models import Annotation
from images.models import Image
from visualization.forms import create_image_filter_form


def get_request_images(request, source):
    image_form = create_image_filter_form(
        request.POST, source, has_annotation_status=True)
    if image_form:
        if image_form.is_valid():
            image_set = image_form.get_images()
        else:
            # This is an unusual error case where the current image search
            # worked for the Browse-images page load, but not for the
            # subsequent export.
            raise ValidationError
    else:
        image_set = Image.objects.filter(source=source)

    image_set = image_set.order_by('metadata__name')
    return image_set


def create_csv_stream_response(filename):
    """
    Create a downloadable-CSV-file HTTP response.
    The response object can be used as a stream,
    which a CSV writer can write to.

    https://docs.djangoproject.com/en/dev/ref/request-response/#telling-the-browser-to-treat-the-response-as-a-file-attachment
    """
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = \
        'attachment;filename="{filename}"'.format(filename=filename)
    return response


def write_annotations_csv(writer, image_set, full):
    # Header row
    row = ["Name", "Row", "Column", "Label"]
    if full:
        row.extend(["Annotator", "Date annotated"])
    writer.writerow(row)

    # Annotation data for the image set, one row per annotation
    # Order by image name, then point number
    annotations = Annotation.objects \
        .filter(image__in=image_set) \
        .order_by('image__metadata__name', 'point__point_number')

    for annotation in annotations:
        row = [
            annotation.image.metadata.name,
            annotation.point.row,
            annotation.point.column,
            annotation.label_code,
        ]
        if full:
            row.extend([
                annotation.user.username,
                # Truncate date precision at seconds
                annotation.annotation_date.replace(microsecond=0),
            ])
        writer.writerow(row)


def write_labelset_csv(writer, source):
    # Header row
    row = ["Label ID", "Short Code"]
    writer.writerow(row)

    if not source.labelset:
        # This shouldn't happen unless the user does URL crafting to get here
        # for some reason. Not a big deal though, we'll just return a CSV
        # with no data rows.
        return

    labels = source.labelset.get_labels().order_by('code')

    for label in labels:
        row = [
            label.global_label_id,
            label.code,
        ]
        writer.writerow(row)
