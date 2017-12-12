import csv
from io import BytesIO
from zipfile import ZipFile

try:
    # Python 3.4+
    from pathlib import Path
except ImportError:
    # Python 2.x with pathlib2 package
    from pathlib2 import Path

from django.core.exceptions import ValidationError
from django.http import HttpResponse

from annotations.model_utils import AnnotationAreaUtils
from annotations.models import Annotation
from images.models import Image, Point
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


def create_stream_response(content_type, filename):
    """
    Create a downloadable-file HTTP response.
    The response object can be used as a stream, which a file writer
    can write to.

    https://docs.djangoproject.com/en/dev/ref/request-response/#telling-the-browser-to-treat-the-response-as-a-file-attachment
    """
    response = HttpResponse(content_type=content_type)
    response['Content-Disposition'] = \
        'attachment;filename="{filename}"'.format(filename=filename)
    return response

def create_csv_stream_response(filename):
    return create_stream_response('text/csv', filename)

def create_zip_stream_response(filename):
    # https://stackoverflow.com/a/29539722/
    return create_stream_response('application/zip', filename)


def create_zipped_cpcs_stream_response(image_set, cpc_prefs, filename):
    cpc_names_and_streams = []
    for img in image_set:
        cpc_stream = BytesIO()
        write_annotations_cpc(cpc_stream, img, cpc_prefs)
        # TODO: Check CPCe behavior to see how to make the cpc filename.
        # Think we should strip the ext and put .cpc on, but not 100% sure.
        cpc_filename = img.metadata.name
        cpc_names_and_streams.append((cpc_filename, cpc_stream))

    response = create_zip_stream_response(filename)
    write_zip(response, cpc_names_and_streams)
    return response


def write_annotations_cpc(cpc_stream, img, cpc_prefs):
    """
    Write a CPC from scratch.
    :param cpc_stream: An IO stream object.
    :param img: An Image model object.
    :param cpc_prefs:
      CPC 'preferences' indicated by previous CPC uploads to this source.
      Includes code file path, image directory, and CPCe window dimensions.
      These are not important to usage of the image within CoralNet, but they
      are important for exporting back to CPC as seamlessly as possible.
    :return:
    """
    # Each line is a series of comma-separated tokens, so the CSV module works
    # well enough.
    # Some tokens are quoted and some aren't, seemingly without checking for
    # presence of spaces, etc. We'll handle quotes on our own to ensure we
    # match this behavior.
    writer = csv.writer(cpc_stream, quotechar=None, quoting=csv.QUOTE_NONE)

    # Line 1: Environment info and image dimensions
    # TODO: Not sure if the code filepath gets abbreviated with a tilde in some
    # cases. Think I've seen that before but not sure. -Stephen
    local_image_path = Path(cpc_prefs[u'local_image_dir'], img.metadata.name)
    row = [
        u'"' + cpc_prefs[u'local_code_filepath'] + u'"',
        u'"' + str(local_image_path) + u'"',
        img.original_width * 15,
        img.original_height * 15,
        cpc_prefs[u'display_width'] * 15,
        cpc_prefs[u'display_height'] * 15,
    ]
    writer.writerow(row)

    # Lines 2-5: Annotation area bounds.
    # <x from left>,<y from top> in pixels-times-15 units.
    # Order: Bottom left, bottom right, top right, top left.
    # Get from the image model if present, otherwise make it the whole image.

    anno_area = AnnotationAreaUtils.db_format_to_numbers(
        img.metadata.annotation_area)
    anno_area_type = anno_area.pop(u'type')
    if anno_area_type == AnnotationAreaUtils.TYPE_PIXELS:
        # This is the format we want
        pass
    elif anno_area_type == AnnotationAreaUtils.TYPE_PERCENTAGES:
        # Convert to pixels
        anno_area = AnnotationAreaUtils.percentages_to_pixels(
            width=img.original_width, height=img.original_height, **anno_area)
    elif anno_area_type == AnnotationAreaUtils.TYPE_IMPORTED:
        # Unspecified; just use the whole image
        anno_area = dict(
            # TODO: Check
            min_x=1, max_x=img.original_width,
            min_y=1, max_y=img.original_height)
    bound_left = (anno_area[u'min_x']-1) * 15
    bound_right = (anno_area[u'max_x']-1) * 15
    bound_top = (anno_area[u'min_y']-1) * 15  # TODO: Check
    bound_bottom = (anno_area[u'max_y']-1) * 15  # TODO: Check
    writer.writerow([bound_left, bound_bottom])
    writer.writerow([bound_right, bound_bottom])
    writer.writerow([bound_right, bound_top])
    writer.writerow([bound_left, bound_top])

    # Line 6: number of points
    points = Point.objects.filter(image=img)
    writer.writerow([points.count()])

    # Next num_points lines: point positions.
    # <x from left, y from top> of each point in numerical order,
    # seemingly using the x15 scaling.
    # CPCe point positions are on a scale of 15 units = 1 pixel, and
    # the positions start from 0, not 1.
    for point in points:
        point_left = (point.column-1) * 15
        point_top = (point.row-1) * 15
        row = [point_left, point_top]
        writer.writerow(row)

    # Next num_points lines: point labels.
    # "<point number/letter>","<label code>","Notes","<notes code>"
    # Assumption: label code in CoralNet source's labelset == label code
    # in the .cpc file (case insensitive).
    for point in points:
        row = [point.point_number, point.label_code, u'Notes', u'']
        row = [u'"{s}"'.format(s=s) for s in row]
        writer.writerow(row)

    # Next 28 lines: header fields.
    for _ in range(28):
        writer.writerow([u'" "'])


def write_zip(zip_stream, names_and_streams):
    """
    Write a zip file to a stream.
    :param zip_stream:
      The file stream to write the zip file to.
    :param names_and_streams:
      Zip contents as a list of (filename, byte stream) tuples.
      Filename is the name that the file will have in the zip archive.
      A byte stream should be a BytesIO object.
    :return:
      None.
    """
    zip_file = ZipFile(zip_stream, 'w')
    for filename, file_stream in names_and_streams:
        # write() takes a filename. writestr() takes a data string, which
        # seems more suitable for the temporary files we use in
        # export functions.
        zip_file.writestr(filename, file_stream.getvalue())


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
