import codecs
from collections import OrderedDict
import csv
from io import StringIO

# PyCharm may warn that this isn't declared in __all__, but this import
# simply matches BS4's docs as of 2018/12:
# https://www.crummy.com/software/BeautifulSoup/bs4/doc/#unicode-dammit
from bs4 import UnicodeDammit
from django.urls import reverse

from annotations.models import ImageAnnotationInfo
from images.forms import MetadataForm
from images.models import Metadata, Image
from images.utils import generate_points, aux_label_name_collisions, \
    metadata_field_names_to_labels
from vision_backend.models import Features
from lib.exceptions import FileProcessError


def text_file_to_unicode_stream(text_file):
    # Detect charset and convert to Unicode as needed.
    unicode_text = UnicodeDammit(text_file.read()).unicode_markup
    # Convert the text into a line-by-line stream.
    return StringIO(unicode_text, newline='')


# TODO: See if this function can be re-used for metadata and annotation upload.
def csv_to_dict(
        csv_stream, required_columns, optional_columns,
        key_columns, multiple_rows_per_key):
    reader = csv.reader(csv_stream, dialect='excel')

    # Read the first row, which should have column headers.
    column_headers = next(reader)
    # There could be a UTF-8 BOM character at the start of the file.
    # Strip it in that case.
    column_headers[0] = column_headers[0].lstrip(
        codecs.BOM_UTF8.decode())
    # Strip whitespace in general.
    column_headers = [h.strip() for h in column_headers]

    # Ensure column header recognition is case insensitive.
    column_headers = [h.lower() for h in column_headers]

    # Enforce required column headers.
    required_column_headers = [h for key, h in required_columns]
    for h in required_column_headers:
        if h.lower() not in column_headers:
            raise FileProcessError(
                "CSV must have a column called {h}".format(h=h))

    # Map column text headers to string keys we want in the result dict.
    # Ignore columns we don't recognize. We'll indicate this by making the
    # column key None.
    recognized_columns = required_columns + optional_columns
    column_headers_to_keys = dict(
        (h.lower(), key) for key, h in recognized_columns)
    column_keys = [
        column_headers_to_keys.get(h, None)
        for h in column_headers
    ]

    # Use these later.
    required_column_keys = [key for key, header in required_columns]
    column_keys_to_headers = dict(
        (k, h) for k, h in recognized_columns)

    csv_data = OrderedDict()

    # Read the data rows.
    for row_number, row in enumerate(reader, start=2):
        # strip() removes leading/trailing whitespace from the CSV value.
        # A column key of None indicates that we're ignoring that column.
        row_data = OrderedDict(
            (k, value.strip())
            for (k, value) in zip(column_keys, row)
            if k is not None
        )

        # Enforce presence of a value for each required column.
        for k in required_column_keys:
            if row_data[k] == '':
                raise FileProcessError(
                    "CSV row {n}: Must have a value for {h}".format(
                        n=row_number, h=column_keys_to_headers[k]))

        # "Key columns" are the columns that 'identify' each row. There must be
        # at least one key column name given. More than one can be given.
        if len(key_columns) > 1:
            data_key = tuple([row_data[col] for col in key_columns])
        else:
            data_key = row_data[key_columns[0]]

        if multiple_rows_per_key:
            # A defaultdict could make this a bit cleaner, but there's no
            # ordered AND default dict built into Python.
            if data_key not in csv_data:
                csv_data[data_key] = []
            csv_data[data_key].append(row_data)
        else:
            # Only one data value allowed per key.
            if data_key in csv_data:
                key_headers = " + ".join(
                    [column_keys_to_headers[col] for col in key_columns])
                raise FileProcessError(
                    "More than one row with the same {key_headers}:"
                    " {data_key}".format(
                        key_headers=key_headers,
                        data_key=data_key))
            csv_data[data_key] = row_data

    if len(csv_data) == 0:
        raise FileProcessError("No data rows found in the CSV.")

    return csv_data


def metadata_csv_to_dict(csv_stream, source):
    """
    Go from metadata CSV file stream to a dict of metadata dicts.
    The first CSV row is assumed to have metadata field labels like
    "Date", "Aux3", and "White balance card".

    DictReader is not used here because (1) it can't return an OrderedDict,
    and (2) the fact that column names need to be transformed to get the
    dict keys makes usage a bit clunky.
    """
    reader = csv.reader(csv_stream, dialect='excel')

    # Read the first row, which should have column names.
    column_names = next(reader)
    # There could be a UTF-8 BOM character at the start of the file.
    # Strip it in that case.
    column_names[0] = column_names[0].lstrip(codecs.BOM_UTF8.decode())
    column_names = [n.lower().strip() for n in column_names]

    # The column names are field labels (e.g. Date) while we want
    # dicts of the metadata model fields' names (e.g. photo_date).
    #
    # lower() is used to tolerate the CSV column names being in a different
    # case from the model fields' names.
    #
    # If a column name doesn't match any metadata field, we'll use
    # a field name of None to indicate that we're ignoring that column.
    field_names_to_labels = metadata_field_names_to_labels(source)
    field_labels_to_names = dict(
        (v.lower(), k)
        for k, v in field_names_to_labels.items()
    )
    fields_of_columns = [
        field_labels_to_names.get(label, None)
        for label in column_names
    ]

    dupe_labels = aux_label_name_collisions(source)
    if dupe_labels:
        raise FileProcessError(
            "More than one metadata field uses the label '{}'."
            " Your auxiliary fields' names must be unique"
            " and different from the default metadata fields.".format(
                dupe_labels[0]))

    if 'name' not in column_names:
        raise FileProcessError("CSV must have a column called Name")

    if len(set(fields_of_columns) - {None}) <= 1:
        # If we subtract the ignored columns,
        # all we are left with is the name column
        raise FileProcessError(
            "CSV must have at least one metadata column other than Name")

    csv_metadata = OrderedDict()
    image_names_seen = set()

    # Read the rest of the rows, which have metadata for one image per row.
    for row in reader:
        # Make a metadata dict for one image,
        # e.g. {photo_date='2016-06-12', camera='Nikon', ...}
        # A field name of None indicates that we're ignoring that column.
        # strip() removes leading/trailing whitespace from the CSV value.
        metadata_for_image = OrderedDict(
            (k, v.strip())
            for (k, v) in zip(fields_of_columns, row)
            if k is not None
        )

        image_name = metadata_for_image['name']
        if image_name in image_names_seen:
            raise FileProcessError(
                "More than one row with the same image name: {}".format(
                    image_name))
        image_names_seen.add(image_name)

        csv_metadata[image_name] = metadata_for_image

    verified_csv_metadata = metadata_csv_verify_contents(csv_metadata, source)

    return verified_csv_metadata


def metadata_csv_verify_contents(csv_metadata_by_image_name, source):
    """
    Argument dict is indexed by image name. We'll create a new dict indexed
    by metadata id, while verifying image existence and metadata validity.
    """
    csv_metadata = OrderedDict()

    for image_name, metadata_for_image in csv_metadata_by_image_name.items():

        try:
            metadata = \
                Metadata.objects.get(name=image_name, image__source=source)
        except Metadata.DoesNotExist:
            # This filename isn't in the source. Just skip this CSV row
            # without raising an error. It could be an image the user is
            # planning to upload later, or an image they're not planning
            # to upload but are still tracking in their records.
            continue

        # Use this form just to check the metadata, not to save anything.
        metadata_form = MetadataForm(
            metadata_for_image, instance=metadata, source=source)

        if not metadata_form.is_valid():
            # One of the filenames' metadata is not valid. Get one
            # error message and return that.
            for field_name, error_messages in metadata_form.errors.items():
                field_label = metadata_form.fields[field_name].label
                if len(error_messages) > 0:
                    error_message = error_messages[0]
                    raise FileProcessError(
                        "({filename} - {field_label}) {message}".format(
                            filename=metadata_for_image['name'],
                            field_label=field_label,
                            message=error_message,
                        )
                    )

        csv_metadata[metadata.pk] = metadata_for_image

    if len(csv_metadata) == 0:
        raise FileProcessError("No matching filenames found in the source")

    return csv_metadata


def metadata_preview(csv_metadata, source):
    table = []
    details = dict()
    field_names_to_labels = metadata_field_names_to_labels(source)
    num_fields_replaced = 0

    for metadata_id, metadata_for_image in csv_metadata.items():

        if len(table) == 0:
            # Column headers: Get the relevant field names from any data row
            # (the first one in our case), and go from field names to labels
            table.append(
                [field_names_to_labels[name]
                 for name in metadata_for_image.keys()]
            )

        metadata = Metadata.objects.get(pk=metadata_id, image__source=source)

        # Use this form just to preview the metadata, not to save anything.
        metadata_form = MetadataForm(
            metadata_for_image, instance=metadata, source=source)
        # We already validated previously, so this SHOULD be valid.
        if not metadata_form.is_valid():
            raise ValueError("Metadata became invalid for some reason.")

        row = []
        for field_name in metadata_for_image.keys():
            new_value = str(metadata_form.cleaned_data[field_name] or '')
            old_value = str(metadata_form.initial[field_name] or '')

            if (not old_value) or (old_value == new_value):
                # Old value is blank, or old value is equal to new value.
                # No value is being replaced here.
                row.append(new_value)
            else:
                # Old value is present and different; include this in the
                # display so the user knows what's going to be replaced.
                row.append([new_value, old_value])
                num_fields_replaced += 1
        table.append(row)

    details['numImages'] = len(csv_metadata)
    details['numFieldsReplaced'] = num_fields_replaced

    return table, details


def annotations_csv_to_dict(csv_stream, source):
    """
    Go from annotations CSV file stream to
    dict of (image ids -> lists of dicts with keys row, column, (opt.) label).

    The first CSV row is assumed to have column headers.
    Valid headers: Name, Row, Column, Label (not case sensitive)
    Label is optional.
    """
    reader = csv.reader(csv_stream, dialect='excel')

    # Read the first row, which should have column names.
    column_names = next(reader)
    # There could be a UTF-8 BOM character at the start of the file.
    # Strip it in that case.
    column_names[0] = column_names[0].lstrip(codecs.BOM_UTF8.decode())
    column_names = [name.lower().strip() for name in column_names]

    required_field_names = ['name', 'row', 'column']
    field_names = required_field_names + ['label']
    fields_of_columns = [
        name if name in field_names else None
        for name in column_names
    ]

    for name in required_field_names:
        if name not in column_names:
            raise FileProcessError(
                "CSV must have a column called {name}".format(
                    name=name.title()))

    csv_annotations = OrderedDict()

    # Read the rest of the rows. Each row has data for one point.
    for row in reader:
        csv_point_dict = OrderedDict(
            (k, v.strip())
            for (k, v) in zip(fields_of_columns, row)
            if k is not None and v != ''
        )

        for name in required_field_names:
            if name not in csv_point_dict:
                raise FileProcessError(
                    "CSV row {line_num} is missing a {name} value".format(
                        line_num=reader.line_num, name=name.title()))

        image_name = csv_point_dict.pop('name')
        if image_name not in csv_annotations:
            csv_annotations[image_name] = []

        csv_annotations[image_name].append(csv_point_dict)

    # So far we've checked the CSV formatting. Now check the validity
    # of the contents.
    csv_annotations = annotations_csv_verify_contents(csv_annotations, source)

    return csv_annotations


def annotations_csv_verify_contents(csv_annotations, source):
    """
    Argument dict is indexed by image name. We'll create a new dict indexed
    by image id, while verifying image existence, row, column, and label.
    """
    annotations = OrderedDict()

    for image_name, annotations_for_image in csv_annotations.items():
        try:
            img = Image.objects.get(metadata__name=image_name, source=source)
        except Image.DoesNotExist:
            # This filename isn't in the source. Just skip it
            # without raising an error. It could be an image the user is
            # planning to upload later, or an image they're not planning
            # to upload but are still tracking in their records.
            continue

        for point_number, point_dict in enumerate(annotations_for_image, 1):

            # Check that row/column are integers within the image dimensions.

            point_error_prefix = \
                "For image {image_name}, point {point_number}:".format(
                    image_name=image_name, point_number=point_number)

            row_str = point_dict['row']
            try:
                row = int(row_str)
                if row < 0:
                    raise ValueError
            except ValueError:
                raise FileProcessError(
                    point_error_prefix +
                    " Row should be a non-negative integer, not {row}".format(
                        row=row_str))

            column_str = point_dict['column']
            try:
                column = int(column_str)
                if column < 0:
                    raise ValueError
            except ValueError:
                raise FileProcessError(
                    point_error_prefix +
                    " Column should be a non-negative integer,"
                    " not {column}".format(
                        column=column_str))

            if row > img.max_row:
                raise FileProcessError(
                    point_error_prefix +
                    " Row value is {row},"
                    " but the image is only {height} pixels high"
                    " (accepted values are 0~{max_row})".format(
                        row=row, height=img.original_height,
                        max_row=img.max_row))

            if column > img.max_column:
                raise FileProcessError(
                    point_error_prefix +
                    " Column value is {column},"
                    " but the image is only {width} pixels wide"
                    " (accepted values are 0~{max_column})".format(
                        column=column, width=img.original_width,
                        max_column=img.max_column))

            if 'label' in point_dict:
                # Check that the label is in the labelset
                label_code = point_dict['label']
                if not source.labelset.get_global_by_code(label_code):
                    raise FileProcessError(
                        point_error_prefix +
                        " No label of code {code} found"
                        " in this source's labelset".format(
                            code=label_code))

        annotations[img.pk] = annotations_for_image

    if len(annotations) == 0:
        raise FileProcessError("No matching image names found in the source")

    return annotations


def annotations_preview(csv_annotations, source):
    table = []
    details = dict()
    total_csv_points = 0
    total_csv_annotations = 0
    num_images_with_existing_annotations = 0

    for image_id, points_list in csv_annotations.items():

        img = Image.objects.get(pk=image_id, source=source)
        preview_dict = dict(
            name=img.metadata.name,
            link=reverse('annotation_tool', kwargs=dict(image_id=img.pk)),
        )

        num_csv_points = len(points_list)
        total_csv_points += num_csv_points
        num_csv_annotations = \
            sum(1 for point_dict in points_list if 'label' in point_dict)
        total_csv_annotations += num_csv_annotations
        preview_dict['createInfo'] = \
            "Will create {points} points, {annotations} annotations".format(
                points=num_csv_points, annotations=num_csv_annotations)

        num_existing_annotations = img.annotation_set.confirmed().count()
        if num_existing_annotations > 0:
            preview_dict['deleteInfo'] = \
                "Will delete {annotations} existing annotations".format(
                    annotations=num_existing_annotations)
            num_images_with_existing_annotations += 1

        table.append(preview_dict)

    details['numImages'] = len(csv_annotations)
    details['totalPoints'] = total_csv_points
    details['totalAnnotations'] = total_csv_annotations
    details['numImagesWithExistingAnnotations'] = \
        num_images_with_existing_annotations

    return table, details


def upload_image_process(image_file, image_name, source, current_user):

    metadata_obj = Metadata(
        name=image_name,
        annotation_area=source.image_annotation_area,
    )
    metadata_obj.save()

    # Save the image into the DB
    img = Image(
        original_file=image_file,
        uploaded_by=current_user,
        point_generation_method=source.default_point_generation_method,
        metadata=metadata_obj,
        source=source,
    )
    img.save()

    annotation_info = ImageAnnotationInfo(image=img)
    annotation_info.save()

    features = Features(image=img)
    features.save()

    # Generate and save points
    generate_points(img)

    return img


def find_dupe_image(source, image_name):
    """
    Sees if the given source already has an image with this name.

    If a duplicate image was found, returns that duplicate.
    If no duplicate was found, returns None.
    """
    image_matches = Image.objects.filter(
        source=source, metadata__name=image_name)

    if len(image_matches) >= 1:
        return image_matches[0]
    else:
        return None
