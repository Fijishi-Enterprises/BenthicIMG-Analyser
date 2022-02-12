from collections import OrderedDict
import csv
import functools
from io import StringIO
from pathlib import PureWindowsPath
import re

from annotations.model_utils import AnnotationAreaUtils
from export.utils import create_zip_stream_response, write_zip
from images.models import Point
from lib.exceptions import FileProcessError


def annotations_cpcs_to_dict_read_csv_row(
        reader, cpc_filename, num_tokens_expected):
    """
    Helper for annotations_cpcs_to_dict().
    Basically like calling next(reader), but with more controlled error
    handling.
    :param reader: A CSV reader object.
    :param cpc_filename: The filename of the .cpc file we're reading.
     Used for error messages.
    :param num_tokens_expected: Number of tokens expected in this CSV row.
    :return: iterable of the CSV tokens, stripped of leading and
     trailing whitespace.
    """
    try:
        row_tokens = [token.strip() for token in next(reader)]
    except StopIteration:
        raise FileProcessError(
            "File {cpc_filename} seems to have too few lines.".format(
                cpc_filename=cpc_filename))

    if len(row_tokens) != num_tokens_expected:
        raise FileProcessError((
            "File {cpc_filename}, line {line_num} has"
            " {num_tokens} comma-separated tokens, but"
            " {num_tokens_expected} were expected.").format(
                cpc_filename=cpc_filename,
                line_num=reader.line_num,
                num_tokens=len(row_tokens),
                num_tokens_expected=num_tokens_expected))

    return row_tokens


def annotations_cpcs_to_dict(cpc_names_and_streams, source, plus_notes):
    """
    :param cpc_names_and_streams: An iterable of Coral Point Count .cpc files
      as (file name, Unicode stream) tuples. One .cpc corresponds to one image.
    :param source: The source these .cpc files correspond to.
    :param plus_notes: Boolean option on whether to interpret the + char as
      an ID/Notes separator.
    :return: A dict of relevant info, with the following keys::
      annotations: dict of (image ids -> lists of dicts with keys row,
        column, (opt.) label).
      cpc_contents: dict of image ids -> .cpc's full contents as a string
      code_filepath: Local path to CPCe code file used by one of the .cpc's.
        Since CPCe is Windows only, this is going to be a Windows path.
      image_dir: Local path to image directory used by one of the .cpc's.
        Again, a Windows path. Ending slash can be present or not.
    Throws a FileProcessError if a .cpc has a problem.
    """

    cpc_dicts = []
    code_filepath = None

    for cpc_name, cpc_stream in cpc_names_and_streams:

        cpc_dict = dict(cpc_filename=cpc_name)

        # Each line of a .cpc file is like a CSV row.
        #
        # But different lines have different kinds of values, so we'll go
        # through the lines with next() instead of with a for loop.
        reader = csv.reader(cpc_stream, delimiter=',', quotechar='"')
        read_csv_row_curried = functools.partial(
            annotations_cpcs_to_dict_read_csv_row, reader, cpc_name)

        # Line 1
        code_filepath, image_filepath, width, height, _, _ = \
            read_csv_row_curried(6)
        cpc_dict['image_filepath'] = image_filepath
        cpc_dict['image_width_in_cpce_scale'] = width
        cpc_dict['image_height_in_cpce_scale'] = height

        # Lines 2-5; don't need any info from these,
        # but they should have 2 tokens each
        for _ in range(4):
            read_csv_row_curried(2)

        # Line 6: number of points
        token = read_csv_row_curried(1)[0]
        try:
            num_points = int(token)
            if num_points <= 0:
                raise ValueError
        except ValueError:
            raise FileProcessError((
                "File {cpc_filename}, line {line_num} is supposed to have"
                " the number of points, but this line isn't a"
                " positive integer: {token}").format(
                    cpc_filename=cpc_name,
                    line_num=reader.line_num,
                    token=token))

        # Next num_points lines: point positions. x (column), then y (row).
        cpc_dict['points'] = []
        for _ in range(num_points):
            x_str, y_str = read_csv_row_curried(2)
            cpc_dict['points'].append(dict(x_str=x_str, y_str=y_str))

        # Next num_points lines: point labels.
        # We're taking advantage of the fact that the previous section
        # and this section are both in point-number order. As long as we
        # maintain that order, we assign labels to the correct points.
        for point_index in range(num_points):
            _, cpc_id, _, cpc_notes = read_csv_row_curried(4)
            if cpc_id:
                if cpc_notes and plus_notes:
                    # Assumption: label code in CoralNet source's labelset
                    # == {ID}+{Notes} in the .cpc file (case insensitive).
                    cpc_dict['points'][point_index]['label'] = \
                        f'{cpc_id}+{cpc_notes}'
                else:
                    # Assumption: label code in CoralNet source's labelset
                    # == label code in the .cpc file (case insensitive).
                    cpc_dict['points'][point_index]['label'] = cpc_id

        cpc_stream.seek(0)
        cpc_dict['cpc_content'] = cpc_stream.read()

        cpc_dicts.append(cpc_dict)

    # So far we've checked the .cpc formatting. Now check the validity
    # of the contents.
    cpc_annotations, cpc_contents, cpc_filenames, image_dir = \
        annotations_cpc_verify_contents(cpc_dicts, source)

    return dict(
        annotations=cpc_annotations,
        cpc_contents=cpc_contents,
        cpc_filenames=cpc_filenames,
        code_filepath=code_filepath,
        image_dir=image_dir,
    )


def annotations_cpc_verify_contents(cpc_dicts, source):
    """
    Argument dict is a list of dicts, one dict per .cpc file.

    We'll create a new annotations dict indexed
    by image id, while verifying image existence, row, column, and label.

    While we're at it, we'll also make a dict from image id to .cpc contents.
    """
    annotations = OrderedDict()
    cpc_contents = OrderedDict()
    cpc_filenames = OrderedDict()
    image_names_to_cpc_filenames = dict()
    image_dir = None

    for cpc_dict in cpc_dicts:

        cpc_filename = cpc_dict['cpc_filename']

        # The image filepath follows the rules of the OS running CPCe,
        # not the rules of the server OS. So we don't use Path.
        # CPCe only runs on Windows, so we can assume it's a Windows
        # path. That means using PureWindowsPath (WindowsPath can only
        # be instantiated on a Windows OS).
        cpc_image_filepath = PureWindowsPath(cpc_dict['image_filepath'])
        image_filename = cpc_image_filepath.name

        # Match up the CPCe image filepath to an image name on CoralNet.
        #
        # Let's say the image filepath is D:\Site A\Transect 1\01.jpg
        # Example image names:
        # D:\Site A\Transect 1\01.jpg: best match
        # Site A\Transect 1\01.jpg: 2nd best match
        # Transect 1\01.jpg: 3rd best match
        # 01.jpg: 4th best match
        # Transect 1/01.jpg: same as with backslash
        # /Transect 1/01.jpg: same as without leading slash
        # 23.jpg: non-match 1
        # 4501.jpg: non-match 2
        # sect 1\01.jpg: non-match 3
        #
        # First get names consisting of 01.jpg preceded by /, \, or nothing.
        # This avoids non-match 1 and non-match 2.
        regex_escaped_filename = re.escape(image_filename)
        name_regex = r'^(.*[\\|/])?{fn}$'.format(fn=regex_escaped_filename)
        image_candidates = source.image_set.filter(
            metadata__name__regex=name_regex)
        # Find the best match while avoiding non-match 3.
        img = None
        for image_candidate in image_candidates:
            # Passing through PWP ensures we consistently use backslashes
            # instead of forward slashes
            image_name = str(PureWindowsPath(image_candidate.metadata.name))
            if image_name == str(cpc_image_filepath):
                # Best possible match
                img = image_candidate
                image_dir = ''
                break

            # Iterate over parents, from top (D:\)
            # to bottom (D:\Site A\Transect 1).
            # If a parent combines with image_name to form the full path, then
            # we have a match.
            # TODO: This won't work if image_name starts with a slash; do we
            # want to accommodate that or not?
            for parent in cpc_image_filepath.parents:
                if PureWindowsPath(parent, image_name) == cpc_image_filepath:
                    # It's a match
                    if img and len(img.metadata.name) > len(image_name):
                        # There's already a longer match
                        pass
                    else:
                        # This is the best match so far
                        img = image_candidate
                        image_dir = str(parent)
                    # Move onto the next candidate
                    break

        if img is None:
            # No matching image names in the source. Just skip this CPC
            # without raising an error. It could be an image the user is
            # planning to upload later, or an image they're not planning
            # to upload but are still tracking in their records.
            continue

        image_name = img.metadata.name

        if image_name in image_names_to_cpc_filenames:
            raise FileProcessError((
                "Image {name} has points from more than one .cpc file: {f1}"
                " and {f2}. There should be only one .cpc file"
                " per image.").format(
                    name=image_name,
                    f1=image_names_to_cpc_filenames[image_name],
                    f2=cpc_filename,
                )
            )
        image_names_to_cpc_filenames[image_name] = cpc_filename

        # Detect pixel scale factor - the scale of the x, y units CPCe used to
        # express the point locations.
        #
        # This is normally 15 units per pixel, but
        # that only holds when CPCe runs in 96 DPI. Earlier versions of CPCe
        # (such as CPCe 3.5) did not enforce 96 DPI, so for example, it is
        # possible to run in 120 DPI and get a scale of 12 units per pixel.
        #
        # We can figure out the scale factor by reading the .cpc file's image
        # resolution values. These values are in CPCe's scale, and we know the
        # resolution in pixels, so we can solve for the scale factor.
        try:
            cpce_scale_width = int(cpc_dict['image_width_in_cpce_scale'])
            cpce_scale_height = int(cpc_dict['image_height_in_cpce_scale'])
        except ValueError:
            raise FileProcessError(
                "File {cpc_filename}: The image width and height on line 1"
                " must be integers.".format(cpc_filename=cpc_filename))

        x_scale = cpce_scale_width / img.original_width
        y_scale = cpce_scale_height / img.original_height
        if (not x_scale.is_integer()
                or not y_scale.is_integer()
                or x_scale != y_scale):
            raise FileProcessError(
                "File {cpc_filename}: Could not establish an integer scale"
                " factor from line 1.".format(cpc_filename=cpc_filename))
        pixel_scale_factor = x_scale

        annotations_for_image = []

        for point_number, cpc_point_dict in enumerate(cpc_dict['points'], 1):

            # Check that row/column are integers within the image dimensions.
            # Convert from CPCe units to pixels in the meantime.

            point_error_prefix = \
                "From file {cpc_filename}, point {point_number}:".format(
                    cpc_filename=cpc_filename, point_number=point_number)

            try:
                y = int(cpc_point_dict['y_str'])
                if y < 0:
                    raise ValueError
            except ValueError:
                raise FileProcessError((
                    point_error_prefix +
                    " Row should be a non-negative integer, not"
                    " {y_str}").format(
                        y_str=cpc_point_dict['y_str']))

            try:
                x = int(cpc_point_dict['x_str'])
                if x < 0:
                    raise ValueError
            except ValueError:
                raise FileProcessError((
                    point_error_prefix +
                    " Column should be a non-negative integer, not"
                    " {x_str}").format(
                        x_str=cpc_point_dict['x_str']))

            # CPCe units -> pixels conversion.
            row = int(round(y / pixel_scale_factor))
            column = int(round(x / pixel_scale_factor))
            point_dict = dict(
                row=row,
                column=column,
            )

            if row > img.max_row:
                raise FileProcessError(
                    point_error_prefix +
                    " Row value of {y} corresponds to pixel {row},"
                    " but image {name} is only {height} pixels high"
                    " (accepted values are 0~{max_row})".format(
                        y=y, row=row, name=image_name,
                        height=img.original_height,
                        max_row=img.max_row))

            if column > img.max_column:
                raise FileProcessError(
                    point_error_prefix +
                    " Column value of {x} corresponds to pixel {column},"
                    " but image {name} is only {width} pixels wide"
                    " (accepted values are 0~{max_column})".format(
                        x=x, column=column, name=image_name,
                        width=img.original_width,
                        max_column=img.max_column))

            if 'label' in cpc_point_dict:
                # Check that the label is in the labelset
                label_code = cpc_point_dict['label']
                if not source.labelset.get_global_by_code(label_code):
                    raise FileProcessError(
                        point_error_prefix +
                        " No label of code {code} found"
                        " in this source's labelset".format(
                            code=label_code))
                point_dict['label'] = label_code

            annotations_for_image.append(point_dict)

        annotations[img.pk] = annotations_for_image
        cpc_contents[img.pk] = cpc_dict['cpc_content']
        cpc_filenames[img.pk] = cpc_filename

    if len(annotations) == 0:
        raise FileProcessError("No matching image names found in the source")

    # Note that image_dir was set the last time we picked an image match.
    # So image_dir corresponds to an image match; that's all we want.
    return annotations, cpc_contents, cpc_filenames, image_dir


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
            # PWP ensures that both forward slashes and backslashes are counted
            # as path separators.
            cpc_filename = image_filename_to_cpc_filename(
                PureWindowsPath(img.metadata.name).name)

        # If the image name seems to be a relative path (not just a filename),
        # then use those path directories on the CPC .zip filepath as well.
        image_parent = PureWindowsPath(img.metadata.name).parent
        # If it's a relative path, this appends the directories, else this
        # appends nothing.
        cpc_filepath = str(PureWindowsPath(image_parent, cpc_filename))
        # We've used Windows paths for path-separator flexibility up to this
        # point. Now that we're finished with path manipulations, we'll make
        # sure all separators are forward slashes for .zip export purposes.
        # This makes zip directory tree structures work on every OS. Forward
        # slashes are also required by the .ZIP File Format Specification.
        # https://superuser.com/a/1382853/
        cpc_filepath = cpc_filepath.replace('\\', '/')

        # Convert the stream contents to a string.
        # TODO: If cpc_filepath is already in the cpc_strings dict, then we
        # have a name conflict and need to warn / disambiguate.
        cpc_strings[cpc_filepath] = cpc_stream.getvalue()

    return cpc_strings


def create_zipped_cpcs_stream_response(cpc_strings, zip_filename):
    response = create_zip_stream_response(zip_filename)
    # Convert Unicode strings to byte strings
    cpc_byte_strings = dict([
        (cpc_filename, cpc_content.encode())
        for cpc_filename, cpc_content in cpc_strings.items()
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


def point_to_cpc_export_label_code(point, annotation_filter):
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
        cpc_prefs['local_image_dir'], img.metadata.name)
    row = [
        '"' + cpc_prefs['local_code_filepath'] + '"',
        '"' + str(local_image_path) + '"',
        # Image dimensions. CPCe typically operates in units of 1/15th of a
        # pixel. If a different DPI setting is used in an older version of CPCe
        # (like CPCe 3.5), it can be something else like 1/12th. But we'll
        # assume 1/15th for export.
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
    anno_area_type = anno_area.pop('type')
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
            min_x=0, max_x=img.max_column,
            min_y=0, max_y=img.max_row)
    bound_left = anno_area['min_x'] * 15
    bound_right = anno_area['max_x'] * 15
    bound_top = anno_area['min_y'] * 15
    bound_bottom = anno_area['max_y'] * 15
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
    # the positions start from 0.
    for point in points:
        point_left = point.column * 15
        point_top = point.row * 15
        row = [point_left, point_top]
        writer.writerow(row)

    # Next num_points lines: point labels.
    # "<point number/letter>","<label code>","Notes","<notes code>"
    for point in points:
        label_code = point_to_cpc_export_label_code(
            point, cpc_prefs['annotation_filter'])

        if cpc_prefs['label_mapping'] == 'id_and_notes' and '+' in label_code:
            # Assumption: label code in CoralNet source's labelset
            # == {ID}+{Notes} in the .cpc file (case insensitive),
            # and {ID} does not have a + character in it.
            cpc_id, cpc_notes = label_code.split('+', maxsplit=1)
            row = [point.point_number, cpc_id, 'Notes', cpc_notes]
        else:
            # Assumption: label code in CoralNet source's labelset
            # == label code in the .cpc file (case insensitive).
            row = [point.point_number, label_code, 'Notes', '']

        row = ['"{s}"'.format(s=s) for s in row]
        writer.writerow(row)

    # Next 28 lines: header fields.
    for _ in range(28):
        writer.writerow(['" "'])


def write_annotations_cpc_based_on_prev_cpc(cpc_stream, img, cpc_prefs):
    old_cpc = StringIO(img.cpc_content)

    # Line 1: Environment info and image dimensions
    if cpc_prefs['override_filepaths'] == 'yes':
        # Environment info from cpc prefs, and image dimensions from old file.
        old_line = next(old_cpc)
        local_image_path = PureWindowsPath(
            cpc_prefs['local_image_dir'], img.metadata.name)
        tokens = old_line.split(',')
        tokens[0] = '"' + cpc_prefs['local_code_filepath'] + '"'
        tokens[1] = '"' + str(local_image_path) + '"'
        new_line = ','.join(tokens)
        cpc_stream.write(new_line)
    else:
        # Copy from the previously-uploaded cpc.
        cpc_stream.write(next(old_cpc))

    # Lines 2-5: Annotation area bounds. Just copy these.
    for _ in range(4):
        cpc_stream.write(next(old_cpc))

    # 6th line has the point count
    point_count_line = next(old_cpc)
    point_count = int(point_count_line.strip())
    cpc_stream.write(point_count_line)

    # Next point_count lines have the point positions
    for _ in range(point_count):
        cpc_stream.write(next(old_cpc))

    # Next point_count lines have the labels.
    # Replace the label codes (and notes, if applicable) with the data from
    # CoralNet's DB.
    points = Point.objects.filter(image=img).order_by('point_number')

    for point in points:
        old_line = next(old_cpc)
        old_tokens = old_line.split(',')

        label_code = point_to_cpc_export_label_code(
            point, cpc_prefs['annotation_filter'])

        # Change the ID code (and Notes code if applicable), and ensure
        # they're in double quotes.
        # The rest of this line stays the same.
        if cpc_prefs['label_mapping'] == 'id_and_notes':
            # Get Notes from CoralNet's label codes.
            if '+' in label_code:
                cpc_id, cpc_notes = label_code.split('+', maxsplit=1)
            else:
                cpc_id = label_code
                cpc_notes = ''
            # When replacing the last token (notes code), we have to be
            # careful to preserve the newline.
            new_tokens = [
                old_tokens[0], f'"{cpc_id}"',
                old_tokens[2], f'"{cpc_notes}"\r\n']
        else:
            # Do not get Notes from CoralNet's label codes.
            new_tokens = [
                old_tokens[0], f'"{label_code}"',
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


def labelset_has_plus_code(labelset):
    """
    Returns True if the labelset has at least one label code with the
    + character, False otherwise. This is for CPCe upload/export.
    """
    return labelset.get_labels().filter(code__contains='+').exists()
