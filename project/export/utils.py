from __future__ import unicode_literals
from backports import csv
from io import StringIO
import six
from six.moves import range
from zipfile import ZipFile

try:
    # Python 3.4+
    from pathlib import PureWindowsPath
except ImportError:
    # Python 2.x with pathlib2 package
    from pathlib2 import PureWindowsPath

from django.conf import settings
from django.core.exceptions import ValidationError
from django.http import HttpResponse

from annotations.model_utils import AnnotationAreaUtils
from annotations.models import Annotation
from images.models import Image, Point
from images.utils import metadata_field_names_to_labels
from vision_backend.utils import get_label_scores_for_point
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
            raise ValidationError("Image-search parameters were invalid.")
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


def create_cpc_strings(image_set, cpc_prefs):
    # Dict mapping from cpc filenames to cpc file contents as strings.
    cpc_strings = dict()

    for img in image_set:
        # Write .cpc contents to a stream.
        cpc_stream = StringIO()

        if img.cpc_content and img.cpc_filename:
            # A CPC file was uploaded for this image before.
            write_annotations_cpc_based_on_prev_cpc(cpc_stream, img, cpc_prefs)
            # Use the same CPC filename that was used for this image before.
            cpc_filename = img.cpc_filename
        else:
            # No CPC file was uploaded for this image before.
            write_annotations_cpc(cpc_stream, img, cpc_prefs)
            # Make a CPC filename based on the image filename, like CPCe does.
            cpc_filename = image_filename_to_cpc_filename(
                PureWindowsPath(img.metadata.name).name)

        # If the image name seems to be a relative path (not just a filename),
        # then use those path directories on the CPC .zip filepath as well.
        image_parent = PureWindowsPath(img.metadata.name).parent
        # If it's a relative path, this appends the directories, else this
        # appends nothing.
        cpc_filepath = str(PureWindowsPath(image_parent, cpc_filename))

        # Convert the stream contents to a string.
        # TODO: If cpc_filepath is already in the cpc_strings dict, then we
        # have a name conflict and need to warn / disambiguate.
        cpc_strings[cpc_filepath] = cpc_stream.getvalue()

    return cpc_strings


def create_zipped_cpcs_stream_response(cpc_strings, zip_filename):
    response = create_zip_stream_response(zip_filename)
    # Convert Unicode strings to byte strings
    cpc_byte_strings = dict([
        (cpc_filename, cpc_content.encode('utf-8'))
        for cpc_filename, cpc_content in six.iteritems(cpc_strings)
    ])
    write_zip(response, cpc_byte_strings)
    return response


def image_filename_to_cpc_filename(image_filename):
    """
    Take an image filename string and convert to a cpc filename according
    to CPCe's rules. As far as we can tell, it's simple: strip extension,
    add '.cpc'. Examples:
    IMG_0001.JPG -> IMG_0001.cpc
    img 0001.jpg -> img 0001.cpc
    my_image.bmp -> my_image.cpc
    another_image.gif -> another_image.cpc
    """
    cpc_filename = PureWindowsPath(image_filename).stem + '.cpc'
    return cpc_filename


def point_to_cpc_export_label_code(point, annotation_filter=None):
    """
    Normally, annotation export will export ALL annotations, including machine
    annotations of low confidence. This is usually okay because, if users want
    to exclude Unconfirmed annotations when exporting, they can filter images
    to just Confirmed and then export from there.

    However, this breaks down in CPC export's use case: CPC import,
    add confident machine annotations, and then CPC export to continue
    annotating in CPCe. These users will expect to only export the confident
    machine annotations, and confidence is on a per-point basis, not per-image.
    So we need to filter the annotations on a point basis. That's what this
    function is for.

    :param point: A Point model object.
    :param annotation_filter:
      'confirmed_only' to denote that only Confirmed annotations are accepted.
      'confirmed_and_confident' to denote that Unconfirmed annotations above
      the source's confidence threshold are also accepted. Normally, these
      annotations will become Confirmed when you enter the annotation tool for
      that image... but if you're planning to annotate in CPCe, there's no
      other reason to enter the annotation tool!
    :return: Label short code string of the point's annotation, if there is
      an annotation which is accepted by the annotation_filter. Otherwise, ''.
    """
    if annotation_filter is None:
        return point.label_code

    if point.annotation_status_property == 'confirmed':
        # Confirmed annotations are always included
        return point.label_code
    elif (annotation_filter == 'confirmed_and_confident'
          and point.annotation_status_property == 'unconfirmed'):
        # With this annotation_filter, Unconfirmed annotations are included
        # IF they're above the source's confidence threshold
        if point.machine_confidence >= point.image.source.confidence_threshold:
            return point.label_code

    # The annotation filter rejects this annotation, or there is no annotation
    return ''


def write_annotations_cpc(cpc_stream, img, cpc_prefs):
    """
    Write a CPC from scratch.
    :param cpc_stream: An IO stream object.
    :param img: An Image model object.
    :param cpc_prefs:
      CPC 'preferences' indicated by previous CPC uploads to this source.
      Includes code file path and image directory.
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
    local_image_path = PureWindowsPath(
        cpc_prefs[u'local_image_dir'], img.metadata.name)
    row = [
        u'"' + cpc_prefs[u'local_code_filepath'] + u'"',
        u'"' + str(local_image_path) + u'"',
        # Image dimensions. CPCe operates in units of 1/15th of a pixel.
        img.original_width * 15,
        img.original_height * 15,
        # These 2 items seem to be the display width/height that the image
        # was opened at in CPCe. Last opened? Initially opened? Not sure.
        # Is this ever even used when opening the CPC file? As far as we know,
        # no. We'll just arbitrarily set this to 960x720.
        # The CPCe documentation says CPCe works best with 1024x768 resolution
        # and above, so displaying the image itself at 960x720 is roughly
        # around there.
        960 * 15,
        720 * 15,
    ]
    writer.writerow(row)

    # Lines 2-5: Annotation area bounds.
    # <x from left>,<y from top> in units of 1/15th of a pixel.
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
            min_x=1, max_x=img.original_width,
            min_y=1, max_y=img.original_height)
    bound_left = (anno_area[u'min_x']-1) * 15
    bound_right = (anno_area[u'max_x']-1) * 15
    bound_top = (anno_area[u'min_y']-1) * 15
    bound_bottom = (anno_area[u'max_y']-1) * 15
    writer.writerow([bound_left, bound_bottom])
    writer.writerow([bound_right, bound_bottom])
    writer.writerow([bound_right, bound_top])
    writer.writerow([bound_left, bound_top])

    # Line 6: number of points
    points = Point.objects.filter(image=img).order_by('point_number')
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
        row = [point.point_number,
               point_to_cpc_export_label_code(
                   point, cpc_prefs[u'annotation_filter']),
               u'Notes', u'']
        row = [u'"{s}"'.format(s=s) for s in row]
        writer.writerow(row)

    # Next 28 lines: header fields.
    for _ in range(28):
        writer.writerow([u'" "'])


def write_annotations_cpc_based_on_prev_cpc(cpc_stream, img, cpc_prefs):
    old_cpc = StringIO(img.cpc_content)

    # Copy first 5 lines
    for _ in range(5):
        cpc_stream.write(old_cpc.next())

    # 6th line has the point count
    point_count_line = old_cpc.next()
    point_count = int(point_count_line.strip())
    cpc_stream.write(point_count_line)

    # Next point_count lines have the point positions
    for _ in range(point_count):
        cpc_stream.write(old_cpc.next())

    # Next point_count lines have the labels.
    # Replace the label codes with the ones in CoralNet's DB.
    points = Point.objects.filter(image=img).order_by('point_number')

    for point in points:
        old_line = old_cpc.next()
        old_tokens = old_line.split(',')
        # Just change the label code, and ensure it's in double quotes.
        # The other tokens on this line stay the same (point number, notes).
        label_code = point_to_cpc_export_label_code(
            point, cpc_prefs[u'annotation_filter'])
        new_tokens = [
            old_tokens[0], '"{}"'.format(label_code),
            old_tokens[2], old_tokens[3]]
        new_line = ','.join(new_tokens)
        cpc_stream.write(new_line)

    # Copy remaining contents
    cpc_stream.write(old_cpc.read())


def get_previous_cpcs_status(image_set):
    if image_set.exclude(cpc_content='').exists():
        # At least 1 image has a previous CPC
        if image_set.filter(cpc_content='').exists():
            # Some, but not all images have previous CPCs
            return 'some'
        else:
            # All images have previous CPCs
            return 'all'
    else:
        # No images have previous CPCs
        return 'none'


def write_zip(zip_stream, file_strings):
    """
    Write a zip file to a stream.
    :param zip_stream:
      The file stream to write the zip file to.
    :param file_strings:
      Zip contents as a dict of filepaths to byte strings (e.g. result of
      getvalue() on a byte stream).
      Filepath is the path that the file will have in the zip archive.
    :return:
      None.
    """
    zip_file = ZipFile(zip_stream, 'w')
    for filepath, content_string in six.iteritems(file_strings):
        zip_file.writestr(filepath, content_string)


def write_annotations_csv(response, source, image_set, optional_columns):
    """
    :param response: Stream response object which we can write file content to.
    :param source: The source we're exporting annotations for.
    :param image_set: Non-empty queryset of images to write annotations for.
        Images should all be from the source which was also passed in.
    :param optional_columns: List of string keys indicating optional column sets
        to add.
    :return: None. This function simply writes CSV file content to the
        response argument.
    """
    metadata_field_labels = metadata_field_names_to_labels(source)
    metadata_date_aux_fields = [
        'photo_date', 'aux1', 'aux2', 'aux3', 'aux4', 'aux5']
    metadata_other_fields = [
        f for f in metadata_field_labels.keys()
        if f not in [
            'name', 'photo_date', 'aux1', 'aux2', 'aux3', 'aux4', 'aux5']
    ]

    fieldnames = ["Name", "Row", "Column", "Label"]

    if 'annotator_info' in optional_columns:
        fieldnames.extend(["Annotator", "Date annotated"])

    if 'machine_suggestions' in optional_columns:
        for n in range(1, settings.NBR_SCORES_PER_ANNOTATION+1):
            fieldnames.extend([
                "Machine suggestion {n}".format(n=n),
                "Machine confidence {n}".format(n=n),
            ])

    if 'metadata_date_aux' in optional_columns:
        date_aux_labels = [
            metadata_field_labels[name]
            for name in metadata_date_aux_fields
        ]
        # Insert these columns before the Row column
        insert_index = fieldnames.index("Row")
        fieldnames = (
            fieldnames[:insert_index]
            + date_aux_labels
            + fieldnames[insert_index:])

    if 'metadata_other' in optional_columns:
        other_meta_labels = [
            metadata_field_labels[name]
            for name in metadata_other_fields
        ]
        # Insert these columns before the Row column
        insert_index = fieldnames.index("Row")
        fieldnames = (
            fieldnames[:insert_index]
            + other_meta_labels
            + fieldnames[insert_index:])

    writer = csv.DictWriter(response, fieldnames)
    writer.writeheader()

    # Annotation data for the image set, one row per annotation
    # Order by image name, then point number
    annotations = Annotation.objects \
        .filter(image__in=image_set) \
        .order_by('image__metadata__name', 'point__point_number')

    for annotation in annotations:
        row = {
            "Name": annotation.image.metadata.name,
            "Row": annotation.point.row,
            "Column": annotation.point.column,
            "Label": annotation.label_code,
        }

        if 'annotator_info' in optional_columns:
            # Truncate date precision at seconds
            date_annotated = annotation.annotation_date.replace(microsecond=0)
            row.update({
                "Annotator": annotation.user.username,
                "Date annotated": date_annotated,
            })

        if 'machine_suggestions' in optional_columns:
            label_scores = get_label_scores_for_point(
                annotation.point, ordered=True)
            for i in range(settings.NBR_SCORES_PER_ANNOTATION):
                try:
                    score = label_scores[i]
                except IndexError:
                    # We might need to fill in some blank scores. For example,
                    # when the classification system hasn't annotated these
                    # points yet, or when the labelset has fewer than
                    # NBR_SCORES_PER_ANNOTATION labels.
                    score = {'label': "", 'score': ""}
                n = i + 1
                row.update({
                    "Machine suggestion {n}".format(n=n): score['label'],
                    "Machine confidence {n}".format(n=n): score['score'],
                })

        if 'metadata_date_aux' in optional_columns:
            label_value_tuples = []
            for field_name in metadata_date_aux_fields:
                label = metadata_field_labels[field_name]
                value = getattr(annotation.image.metadata, field_name)
                if value is None:
                    value = ""
                label_value_tuples.append((label, value))
            row.update(dict(label_value_tuples))

        if 'metadata_other' in optional_columns:
            label_value_tuples = []
            for field_name in metadata_other_fields:
                label = metadata_field_labels[field_name]
                value = getattr(annotation.image.metadata, field_name)
                if value is None:
                    value = ""
                label_value_tuples.append((label, value))
            row.update(dict(label_value_tuples))

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
