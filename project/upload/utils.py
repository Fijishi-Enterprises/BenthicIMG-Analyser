import codecs
from collections import OrderedDict
import csv
import datetime
import os
import shelve

from django.conf import settings
from django.core.urlresolvers import reverse

from accounts.utils import get_imported_user
from annotations.model_utils import AnnotationAreaUtils
from annotations.models import Label, Annotation
from images.forms import MetadataForm
from images.model_utils import PointGen
from images.models import Metadata, ImageStatus, Image, Point, Source
from images.utils import generate_points, get_aux_metadata_db_value_dict_from_str_list, get_aux_field_names
from lib import str_consts
from lib.exceptions import DirectoryAccessError, FileProcessError
from lib.utils import rand_string


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

    field_labels = field_names_to_labels.values()
    dupe_labels = [
        label for label in field_labels
        if field_labels.count(label) > 1
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

    if len(metadata_field_names_in_column_order) <= 1:
        raise FileProcessError(
            "No metadata columns other than 'Name' found in CSV")

    csv_metadata = dict()
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


def annotations_file_to_python(annoFile, source, expecting_labels):
    """
    Takes: an annotations file

    Returns: the Pythonized annotations:
    A dictionary like this:
    {'Shore1;Reef3;...;2008': [{'row':'695', 'col':'802', 'label':'POR'},
                               {'row':'284', 'col':'1002', 'label':'ALG'},
                               ...],
     'Shore2;Reef5;...;2009': [...]
     ... }

    Checks for: correctness of file formatting, i.e. all words/tokens are there on each line
    (will throw an error otherwise)
    """

    # We'll assume annoFile is an InMemoryUploadedFile, as opposed to a filename of a temp-disk-storage file.
    # If we encounter a case where we have a filename, use the below:
    #annoFile = open(annoFile, 'r')

    # Format args: line number, line contents, error message
    file_error_format_str = str_consts.ANNOTATION_FILE_FULL_ERROR_MESSAGE_FMTSTR

    uniqueLabelCodes = []

    # The order of the words/tokens is encoded here.  If the order ever
    # changes, we should only have to change this part.
    words_format_without_label = get_aux_field_names()
    words_format_without_label += ['date', 'row', 'col']
    words_format_with_label = words_format_without_label + ['label']

    num_words_with_label = len(words_format_with_label)
    num_words_without_label = len(words_format_without_label)

    # The annotation dict needs to be kept on disk temporarily until all the
    # Ajax upload requests are done. Thus, we'll use Python's shelve module
    # to make a persistent dict.
    if not os.access(settings.SHELVED_ANNOTATIONS_DIR, os.R_OK | os.W_OK):
        # Don't catch this error and display it to the user.
        # Just let it become a server error to be e-mailed to the admins.
        raise DirectoryAccessError(
            "The SHELVED_ANNOTATIONS_DIR either does not exist, is not readable, or is not writable. Please rectify this."
        )
    annotation_dict_id = rand_string(10)
    annotation_dict = shelve.open(os.path.join(
        settings.SHELVED_ANNOTATIONS_DIR,
        'source{source_id}_{dict_id}'.format(
            source_id=source.id,
            dict_id=annotation_dict_id,
        ),
    ))

    for line_num, line in enumerate(annoFile, 1):

        # Strip any leading UTF-8 BOM, then strip any
        # leading/trailing whitespace.
        stripped_line = line.lstrip(codecs.BOM_UTF8).strip()

        # Ignore empty lines.
        if stripped_line == '':
            continue

        # Split the line into words/tokens.
        unstripped_words = stripped_line.split(';')
        # Strip leading and trailing whitespace from each token.
        words = [w.strip() for w in unstripped_words]

        # Check that all expected words/tokens are there.
        is_valid_format_with_label = (len(words) == num_words_with_label)
        is_valid_format_without_label = (len(words) == num_words_without_label)
        words_format_is_valid = (
            (expecting_labels and is_valid_format_with_label)
            or (not expecting_labels and (is_valid_format_with_label or is_valid_format_without_label))
        )
        if expecting_labels:
            num_words_expected = num_words_with_label
        else:
            num_words_expected = num_words_without_label

        if not words_format_is_valid:
            annotation_dict.close()
            annoFile.close()
            raise FileProcessError(file_error_format_str.format(
                line_num=line_num,
                line=stripped_line,
                error=str_consts.ANNOTATION_FILE_TOKEN_COUNT_ERROR_FMTSTR.format(
                    num_words_expected=num_words_expected,
                    num_words_found=len(words),
                )
            ))

        # Encode the line data into a dictionary: {'aux1':'Shore2', 'row':'575', ...}
        if is_valid_format_with_label:
            lineData = dict(zip(words_format_with_label, words))
        else:  # valid format without label
            lineData = dict(zip(words_format_without_label, words))

        try:
            row = int(lineData['row'])
            if row <= 0:
                raise ValueError
        except ValueError:
            annotation_dict.close()
            annoFile.close()
            raise FileProcessError(file_error_format_str.format(
                line_num=line_num,
                line=stripped_line,
                error=str_consts.ANNOTATION_FILE_ROW_NOT_POSITIVE_INT_ERROR_FMTSTR.format(row=lineData['row']),
            ))

        try:
            col = int(lineData['col'])
            if col <= 0:
                raise ValueError
        except ValueError:
            annotation_dict.close()
            annoFile.close()
            raise FileProcessError(file_error_format_str.format(
                line_num=line_num,
                line=stripped_line,
                error=str_consts.ANNOTATION_FILE_COL_NOT_POSITIVE_INT_ERROR_FMTSTR.format(column=lineData['col']),
            ))

        if expecting_labels:
            # Check that the label code corresponds to a label in the database
            # and in the source's labelset.
            # Only check this if the label code hasn't been seen before
            # in the annotations file.

            label_code = lineData['label']
            if label_code not in uniqueLabelCodes:

                labelObjs = Label.objects.filter(code=label_code)
                if len(labelObjs) == 0:
                    annotation_dict.close()
                    annoFile.close()
                    raise FileProcessError(file_error_format_str.format(
                        line_num=line_num,
                        line=stripped_line,
                        error=str_consts.ANNOTATION_FILE_LABEL_NOT_IN_DATABASE_ERROR_FMTSTR.format(label_code=label_code),
                    ))

                labelObj = labelObjs[0]
                if labelObj not in source.labelset.labels.all():
                    annotation_dict.close()
                    annoFile.close()
                    raise FileProcessError(file_error_format_str.format(
                        line_num=line_num,
                        line=stripped_line,
                        error=str_consts.ANNOTATION_FILE_LABEL_NOT_IN_LABELSET_ERROR_FMTSTR.format(label_code=label_code),
                    ))

                uniqueLabelCodes.append(label_code)

        # Get and check the photo year to make sure it's valid.
        # We'll assume the year is the first 4 characters of the date.
        year = lineData['date'][:4]
        try:
            datetime.date(int(year),1,1)
        # Year is non-coercable to int, or year is out of range (e.g. 0 or negative)
        except ValueError:
            annotation_dict.close()
            annoFile.close()
            raise FileProcessError(file_error_format_str.format(
                line_num=line_num,
                line=stripped_line,
                error=str_consts.ANNOTATION_FILE_YEAR_ERROR_FMTSTR.format(year=year),
            ))

        # TODO: Check if the row and col in this line are a valid row and col
        # for the image.  Need the image to do that, though...


        # Use the location values and the year to build a string identifier for the image, such as:
        # Shore1;Reef5;...;2008
        valueList = [lineData[name] for name in get_aux_field_names()]
        imageIdentifier = get_image_identifier(valueList, year)

        # Add/update a dictionary entry for the image with this identifier.
        # The dict entry's value is a list of labels.  Each label is a dict:
        # {'row':'484', 'col':'320', 'label':'POR'}
        if not annotation_dict.has_key(imageIdentifier):
            annotation_dict[imageIdentifier] = []

        # Append the annotation as a dict containing row, col, and label
        # (or just row and col, if no labels).
        #
        # Can't append directly to annotation_dict[imageIdentifier], due to
        # how shelved dicts work. So we use this pattern with a temporary
        # variable.
        # See http://docs.python.org/library/shelve.html?highlight=shelve#example
        tmp_data = annotation_dict[imageIdentifier]
        if expecting_labels:
            tmp_data.append(
                dict(row=row, col=col, label=lineData['label'])
            )
        else:
            tmp_data.append(
                dict(row=row, col=col)
            )
        annotation_dict[imageIdentifier] = tmp_data

    annoFile.close()

    return (annotation_dict, annotation_dict_id)


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


def upload_annotations_process(
        imageFile, imageOptionsForm, annotation_dict_id,
        csv_dict_id, metadata_import_form_class,
        annotation_options_form, source, currentUser):

    is_uploading_points_or_annotations = annotation_options_form.cleaned_data['is_uploading_points_or_annotations']

    filename = imageFile.name
    metadata_dict = None
    metadata_obj = Metadata(height_in_cm=source.image_height_in_cm)

    if imageOptionsForm.cleaned_data['specify_metadata'] == 'filenames':

        filename_check_result = check_image_filename(filename, source)
        filename_status = filename_check_result['status']

        if filename_status == 'error':
            # This case should never happen if the pre-upload
            # status checking is doing its job, but just in case...
            return dict(
                status=filename_status,
                message=u"{m}".format(m=filename_check_result['message']),
                link=None,
                title=None,
            )

        # Set the metadata
        metadata_dict = filename_check_result['metadata_dict']

        value_dict = get_aux_metadata_db_value_dict_from_str_list(
            source, metadata_dict['values'])
        photo_date = datetime.date(
            year = int(metadata_dict['year']),
            month = int(metadata_dict['month']),
            day = int(metadata_dict['day'])
        )

        metadata_obj.name = metadata_dict['name']
        metadata_obj.photo_date = photo_date
        for key, value in value_dict.iteritems():
            setattr(metadata_obj, key, value)

    elif imageOptionsForm.cleaned_data['specify_metadata'] == 'csv':

        if not csv_dict_id:
            return dict(
                status='error',
                message=u"{m}".format(m="CSV file was not uploaded."),
                link=None,
                title=None,
            )

        csv_dict_filename = os.path.join(
            settings.SHELVED_ANNOTATIONS_DIR,
            'csv_source{source_id}_{dict_id}.db'.format(
                source_id=source.id,
                dict_id=csv_dict_id,
            ),
        )

        # Corner case: the specified shelved annotation file doesn't exist.
        # Perhaps the file was created a while ago and has been pruned since,
        # or perhaps there is a bug.
        if not os.path.isfile(csv_dict_filename):
            return dict(
                status='error',
                message="CSV file could not be found - if you provided the .csv file a while ago, maybe it just timed out. Please retry the upload.",
                link=None,
                title=None,
            )

        csv_dict = shelve.open(csv_dict_filename)

        #index into the csv_dict with the filename. the str() is to handle
        #the case where the filename is a unicode object instead of a str;
        #unicode objects can't index into dicts.
        filename_str = str(filename)

        if filename_str in csv_dict:

            # There is CSV metadata for this file.

            metadata_dict = csv_dict[str(filename)]
            csv_dict.close()

            # The reason this uses metadata_import_form_class instead of
            # importing MetadataImportForm is that I'm too lazy to deal with the
            # circular-import implications of the latter solution right now.
            # -Stephen
            metadata_import_form = metadata_import_form_class(
                source.id, True, metadata_dict,
            )

            if not metadata_import_form.is_valid():
                return dict(
                    status='error',
                    message="Unknown error with the CSV metadata.",
                    link=None,
                    title=None,
                )

            fields = ['photo_date', 'aux1', 'aux2', 'aux3', 'aux4',
                      'aux5', 'height_in_cm', 'latitude', 'longitude',
                      'depth', 'camera', 'photographer', 'water_quality',
                      'strobes', 'framing', 'balance']

            for field in fields:

                if not field in metadata_import_form.fields:
                    # A location value field that's not in this form
                    continue

                value = metadata_import_form.cleaned_data[field]
                # Check for a non-empty value; don't want empty values to
                # override default values that we've already set on the
                # metadata_obj
                if value:
                    setattr(metadata_obj, field, value)

        else:

            # No CSV metadata for this file.

            csv_dict.close()

        metadata_obj.name = filename

    else:

        # Not specifying any metadata at upload time.
        metadata_obj.name = filename


    image_annotations = None
    has_points_or_annotations = False

    if is_uploading_points_or_annotations:

        # Corner case: somehow, we're uploading with points+annotations and without
        # a checked annotation file specified.  This probably indicates a bug.
        if not annotation_dict_id:
            return dict(
                status='error',
                message=u"{m}".format(m=str_consts.UPLOAD_ANNOTATIONS_ON_AND_NO_ANNOTATION_DICT_ERROR_STR),
                link=None,
                title=None,
            )

        annotation_dict_filename = os.path.join(
            settings.SHELVED_ANNOTATIONS_DIR,
            'source{source_id}_{dict_id}'.format(
                source_id=source.id,
                dict_id=annotation_dict_id,
            ),
        )

        # Corner case: the specified shelved annotation file doesn't exist.
        # Perhaps the file was created a while ago and has been pruned since,
        # or perhaps there is a bug.
        if not os.path.isfile(annotation_dict_filename):
            return dict(
                status='error',
                message="Annotations could not be found - if you provided the .txt file a while ago, maybe it just timed out. Please retry the upload.",
                link=None,
                title=None,
            )


        # Use the location values and the year to build a string identifier for the image, such as:
        # Shore1;Reef5;...;2008
        # Convert to a string (instead of a unicode string) for the shelve key lookup.
        image_identifier = str(get_image_identifier(metadata_dict['values'], metadata_dict['year']))

        annotation_dict = shelve.open(annotation_dict_filename)

        if annotation_dict.has_key(image_identifier):
            image_annotations = annotation_dict[image_identifier]
            has_points_or_annotations = True
        annotation_dict.close()

    if has_points_or_annotations:
        # Image upload with points/annotations

        is_uploading_annotations_not_just_points = annotation_options_form.cleaned_data['is_uploading_annotations_not_just_points']
        imported_user = get_imported_user()

        status = ImageStatus()
        status.save()

        metadata_obj.annotation_area = AnnotationAreaUtils.IMPORTED_STR
        metadata_obj.save()

        img = Image(
            original_file=imageFile,
            uploaded_by=currentUser,
            point_generation_method=PointGen.args_to_db_format(
                point_generation_type=PointGen.Types.IMPORTED,
                imported_number_of_points=len(image_annotations)
            ),
            metadata=metadata_obj,
            source=source,
            status=status,
        )
        img.save()

        # Iterate over this image's annotations and save them.
        point_num = 0
        for anno in image_annotations:

            # Save the Point in the database.
            point_num += 1
            point = Point(row=anno['row'], column=anno['col'], point_number=point_num, image=img)
            point.save()

            if is_uploading_annotations_not_just_points:
                label = Label.objects.filter(code=anno['label'])[0]

                # Save the Annotation in the database, marking the annotations as imported.
                annotation = Annotation(user=imported_user,
                    point=point, image=img, label=label, source=source)
                annotation.save()

        img.status.hasRandomPoints = True
        if is_uploading_annotations_not_just_points:
            img.status.annotatedByHuman = True
        img.status.save()
    else:
        # Image upload, no points/annotations
        image_status = ImageStatus()
        image_status.save()

        metadata_obj.annotation_area = source.image_annotation_area
        metadata_obj.save()

        # Save the image into the DB
        img = Image(original_file=imageFile,
            uploaded_by=currentUser,
            point_generation_method=source.default_point_generation_method,
            metadata=metadata_obj,
            source=source,
            status=image_status,
        )
        img.save()

        # Generate and save points
        generate_points(img)

    success_message = "Uploaded"

    return dict(
        status='ok',
        message=success_message,
        link=reverse('image_detail', args=[img.id]),
        title=img.get_image_element_title(),
        image_id=img.id,
    )


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