import codecs
from collections import OrderedDict
import csv

from django.core.urlresolvers import reverse

from accounts.utils import get_imported_user
from annotations.models import Label, Annotation
from images.forms import MetadataForm
from images.model_utils import PointGen
from images.models import Metadata, ImageStatus, Image, Point, Source
from images.utils import generate_points
from lib.exceptions import FileProcessError


def get_image_identifier(valueList, year):
    """
    Use the location values and the year to build a string identifier for an image:
    Shore1;Reef5;...;2008
    """
    return ';'.join(valueList + [year])


def metadata_csv_fields(source):
    """
    Get an OrderedDict of Metadata field names to field labels.
    e.g. 'photo_date': "Date", 'aux1': "Site", 'camera': "Camera", ...
    """
    return OrderedDict(
        (field_name, field.label)
        for field_name, field
        in MetadataForm(source_id=source.pk).fields.items()
    )


def metadata_obj_to_dict(metadata):
    """
    Go from Metadata DB object to metadata dict.
    """
    source = Image.objects.get(metadata=metadata).source
    return MetadataForm(instance=metadata, source_id=source.pk).initial


def metadata_csv_to_dict(csv_file, source):
    """
    Go from metadata CSV file to a dict of metadata dicts.
    The first CSV row is assumed to have metadata field labels like
    "Date", "Aux3", and "White balance card".

    DictReader is not used here because (1) it can't return an OrderedDict,
    and (2) the fact that column names need to be transformed to get the
    dict keys makes usage a bit clunky.
    """
    # splitlines() is to do system-agnostic handling of newline characters.
    # The csv module can't do that by default (fails on CR only).
    reader = csv.reader(csv_file.read().splitlines(), dialect='excel')

    # Read the first row, which should have column names.
    column_names = next(reader)
    # There could be a UTF-8 BOM character at the start of the file.
    # Strip it in that case.
    column_names[0] = column_names[0].lstrip(codecs.BOM_UTF8)
    column_names_lower = [n.lower() for n in column_names]

    # The column names are field labels (e.g. Date) while we want
    # dicts of the metadata model fields' names (e.g. photo_date).
    #
    # lower() is used to tolerate the CSV column names being in a different
    # case from the model fields' names.
    #
    # If a column name doesn't match any metadata field, we'll use
    # a field name of None to indicate that we're ignoring that column.
    field_names_to_labels = metadata_csv_fields(source)
    field_labels_to_names = dict(
        (v.lower(), k)
        for k, v in field_names_to_labels.items()
    )
    metadata_field_names_in_column_order = [
        field_labels_to_names.get(label, None)
        for label in column_names_lower
    ]

    field_labels_lower = [
        label.lower() for label in field_names_to_labels.values()]
    dupe_labels = [
        label for label in field_labels_lower
        if field_labels_lower.count(label) > 1
    ]
    if dupe_labels:
        raise FileProcessError(
            "More than one metadata field uses the label '{}'."
            " Your auxiliary fields' names must be unique"
            " and different from the default metadata fields.".format(
                dupe_labels[0]))

    dupe_column_names = [
        name for name in column_names_lower
        if column_names_lower.count(name) > 1
    ]
    if dupe_column_names:
        raise FileProcessError(
            "Column name appears more than once: {}".format(
                dupe_column_names[0]))

    if 'name' not in column_names_lower:
        raise FileProcessError("No 'Name' column found in CSV")

    if len(set(metadata_field_names_in_column_order) - {None}) <= 1:
        # If we subtract the ignored columns,
        # all we are left with is the name column
        raise FileProcessError(
            "No metadata columns other than 'Name' found in CSV")

    csv_metadata = OrderedDict()
    image_names_seen = set()

    # Read the rest of the rows, which have metadata for one image per row.
    for row in reader:
        # Make a metadata dict for one image,
        # e.g. {photo_date='2016-06-12', camera='Nikon', ...}
        # A field name of None indicates that we're ignoring that column.
        csv_row_metadata = OrderedDict(
            (k, v)
            for (k, v) in zip(metadata_field_names_in_column_order, row)
            if k is not None
        )

        image_name = csv_row_metadata['name']
        if image_name in image_names_seen:
            raise FileProcessError(
                "More than one row with the same image name: {}".format(
                    image_name))
        image_names_seen.add(image_name)

        try:
            metadata_id = Metadata.objects.get(name=image_name).pk
        except Metadata.DoesNotExist:
            # This filename isn't in the source. Just skip this CSV row
            # without raising an error. It could be an image the user is
            # planning to upload later, or an image they're not planning
            # to upload but are still tracking in their records.
            continue

        csv_metadata[metadata_id] = csv_row_metadata

    if len(csv_metadata) == 0:
        raise FileProcessError("No matching filenames found in the source")

    return csv_metadata


def annotations_csv_to_dict(csv_file, source):
    """
    Go from annotations CSV file to
    dict of (image ids -> lists of dicts with keys row, column, (opt.) label).

    The first CSV row is assumed to have column headers.
    Valid headers: Name, Row, Column, Label (not case sensitive)
    Label is optional.
    """
    # splitlines() is to do system-agnostic handling of newline characters.
    # The csv module can't do that by default (fails on CR only).
    reader = csv.reader(csv_file.read().splitlines(), dialect='excel')

    # Read the first row, which should have column names.
    column_names = next(reader)
    # There could be a UTF-8 BOM character at the start of the file.
    # Strip it in that case.
    column_names[0] = column_names[0].lstrip(codecs.BOM_UTF8)
    column_names = [name.lower() for name in column_names]

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
            (k, v)
            for (k, v) in zip(fields_of_columns, row)
            if k is not None and v is not ''
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
    csv_annotations = annotations_verify_contents(csv_annotations, source)

    return csv_annotations


def annotations_verify_contents(csv_annotations_by_image_name, source):
    """
    Argument dict is indexed by image name. We'll create a new dict indexed
    by image id, while verifying image existence, row, column, and label.
    """
    csv_annotations = OrderedDict()

    if source.labelset:
        labelset_label_codes = set(
            obj.code for obj in source.labelset.labels.all())
    else:
        labelset_label_codes = set()

    for image_name, annotations_for_image \
            in csv_annotations_by_image_name.items():
        try:
            img = Image.objects.get(metadata__name=image_name, source=source)
        except Image.DoesNotExist:
            # This filename isn't in the source. Just skip it
            # without raising an error. It could be an image the user is
            # planning to upload later, or an image they're not planning
            # to upload but are still tracking in their records.
            continue

        for point_dict in annotations_for_image:
            # Check that row/column are within the image dimensions
            row_str = point_dict['row']
            try:
                row = int(row_str)
                if row <= 0:
                    raise ValueError
            except ValueError:
                raise FileProcessError(
                    "Row value is not a positive integer: {row}".format(
                        row=row_str))

            column_str = point_dict['column']
            try:
                column = int(column_str)
                if column <= 0:
                    raise ValueError
            except ValueError:
                raise FileProcessError(
                    "Column value is not a positive integer: {column}".format(
                        column=column_str))

            if img.original_height < row:
                raise FileProcessError(
                    "Row value of {row} is too large"
                    " for image {name}, which has dimensions"
                    " {width} x {height}".format(
                        row=row, name=image_name,
                        width=img.original_width, height=img.original_height))

            if img.original_width < column:
                raise FileProcessError(
                    "Column value of {column} is too large"
                    " for image {name}, which has dimensions"
                    " {width} x {height}".format(
                        column=column, name=image_name,
                        width=img.original_width, height=img.original_height))

            if 'label' in point_dict:
                # Check that the label is in the labelset
                label_code = point_dict['label']
                if label_code not in labelset_label_codes:
                    raise FileProcessError(
                        "No label of code {code} found"
                        " in this source's labelset".format(
                            code=label_code))

        # TODO: Check for multiple points on the same row+col

        csv_annotations[img.pk] = annotations_for_image

    if len(csv_annotations) == 0:
        raise FileProcessError("No matching filenames found in the source")

    return csv_annotations


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

        num_existing_annotations = Annotation.objects.filter(image=img).count()
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


def upload_image_process(imageFile, source, currentUser):

    filename = imageFile.name
    metadata_obj = Metadata(
        name=filename,
        height_in_cm=source.image_height_in_cm,
        annotation_area=source.image_annotation_area,
    )
    metadata_obj.save()

    image_status = ImageStatus()
    image_status.save()

    # Save the image into the DB
    img = Image(
        original_file=imageFile,
        uploaded_by=currentUser,
        point_generation_method=source.default_point_generation_method,
        metadata=metadata_obj,
        source=source,
        status=image_status,
    )
    img.save()

    # Generate and save points
    generate_points(img)

    return img


def find_dupe_image(source, image_name):
    """
    Sees if the given source already has an image with the given arguments.

    :param source: The source to check.
    :param image_name: The image's name; based on its filename.
    :returns: If a duplicate image was found, returns that duplicate.  If no
        duplicate was found, returns None.
    """
    imageMatches = Image.objects.filter(source=source, metadata__name=image_name)

    if len(imageMatches) >= 1:
        return imageMatches[0]
    else:
        return None


def load_archived_csv(source_id, file_):
    """
    This file is a helper for when a user uploads a csv with archived annotations (only valid for the "new" archived annotation file type, namely of format: filenams, row, col, label). 
    It load the .csv file to a dictionary. Option with_labels in {0, 1} indicates whether to upload labels also, or just points.
    """
 
    anndict = {}
    for (filename, r, c, l) in csv.reader(file_):
        if filename not in anndict.keys():
            anndict[filename] = [] #each filename is an entry in the dictionary
        anndict[filename].append((int(r.strip()), int(c.strip()), l.strip())) # annotations for each file is a list of tuples (row, column, label)
 
    return anndict


def check_archived_csv(source_id, anndict, with_labels = True):
    """
    This file is a helper for when a user uploads a .csv file with archived annotations (only valid for the "new" archived annotation file type, namely of format: filenams, row, col, label). 

        It takes an anndict (generated, for example, by load_archived_csv) and checks the following:
        1) Do ALL specified image file names exist in source? 
        2) Is ANY of the specified images already annotated by a human operator?
        3) Are ALL specified labels in the source labelset?
        4) Does ALL row and column specified fit inside the image?
        5) Are there duplicated annotations for ANY image?
    """
    source = Source.objects.get(pk = source_id) # let's fetch the relevant source.
    status = {}
    source_images = set([i.metadata.name for i in source.get_all_images()])
    uploaded_images = set(anndict.keys())

    # Some basic stats
    status['nbr_uploaded_images'] = len(uploaded_images)
    status['nbr_uploaded_annotations'] = sum([len(anndict[fn]) for fn in anndict.keys()])

    # First condition: 
    status['matched_images'] = uploaded_images & source_images

    # Second condition:
    annotated_images = set([i.metadata.name for i in Image.objects.filter(source = source, status__annotatedByHuman = True)])
    status['verified_images'] = annotated_images.intersection(status['matched_images'])

    # Third, fourth, and fifth condition:
    status['unknown_labels'] = set()
    status['bad_locations'] = set()
    status['duplicate_annotations'] = set()
    source_labelset = set([l.code for l in source.labelset.labels.all()])
    for imname in status['matched_images']:
        image = Image.objects.get(source = source, metadata__name = imname)
        annset_image = set() #to check for duplicate row, col locations
        for (row, col, label) in anndict[imname]:
            if (not label in source_labelset) and with_labels:
                status['unknown_labels'].add(label) #this is the condition #3
            if not 0 <= row <= image.original_height or not 0 <= col <= image.original_width:
                status['bad_locations'].add(imname)
            if (row, col) in annset_image:
                status['duplicate_annotations'].add(imname)
            annset_image.add((row, col))

    # Summarize:
    status['can_upload'] = (len(status['matched_images']) > 0 and not status['unknown_labels'] and not status['bad_locations'] and not status['duplicate_annotations'])
    
    return status

def import_archived_annotations(source_id, anndict, with_labels = True):

    source = Source.objects.get(pk = source_id) # let's fetch the relevant source.
    imported_user = get_imported_user() # the imported user.

    images = source.get_all_images().filter(metadata__name__in = list(anndict.keys())) # grab all image that have names in the .csv file.

    for image in images:

        # Start by remove annotations and points for this image
        for ann in Annotation.objects.filter(image=image):
            ann.delete()
        for point in Point.objects.filter(image=image):
            point.delete()
    
        # Next, set image metadata to IMPORTED.
        image.point_generation_method = PointGen.args_to_db_format(
                point_generation_type=PointGen.Types.IMPORTED,
                imported_number_of_points=len(anndict[image.metadata.name])
        )
        image.status.hasRandomPoints = True
        image.status.annotatedByHuman = with_labels
        image.status.save()
        image.after_annotation_area_change() # set the backend status correctly.

        # Iterate over this image's annotations and save them.
        for (point_num, (row, col, code)) in enumerate(anndict[image.metadata.name]):
            
            # Save the Point in the database.
            point = Point(row=row, column=col, point_number=point_num + 1, image=image)
            point.save()

            # and save the Annotation.
            if with_labels:
                label = Label.objects.filter(code=code)[0]
                annotation = Annotation(user=imported_user, point=point, image=image, label=label, source=source)
                annotation.save()