from collections import OrderedDict
import datetime
import math
import random

from django.conf import settings
from django.db.models import Count, Q
from django.urls import reverse

from accounts.utils import get_alleviate_user
from annotations.model_utils import AnnotationAreaUtils
from .model_utils import PointGen
from .models import Source, Point, Image, Metadata


def _get_next_images_queryset(current_image, image_queryset):
    """
    Get the images that are ordered after current_image, based on the
    queryset's ordering.
    """
    # Start this Q object out as 'always False' because we want to make this
    # the starting value of an 'OR' reduce chain.
    # From: https://stackoverflow.com/questions/35893867/
    filter_q = Q(pk__in=[])
    # Start this Q object out as 'always True' because we want to make this
    # the starting value of an 'AND' reduce chain.
    # From: https://stackoverflow.com/questions/33517468/
    previous_keys_equal_q = ~Q(pk__in=[])

    # query.order_by example: ['metadata__name', 'pk']
    #
    # The query we want gets more complicated depending on the number of
    # order_by keys:
    # 1 key: key1 greater
    # 2 keys: key1 greater OR (key1 equal AND key2 greater)
    # 3 keys: key1 greater OR (key1 equal AND key2 greater)
    #   OR (key1 equal AND key2 equal AND key3 greater)
    # Etc.
    for ordering_key in image_queryset.query.order_by:

        descending = ordering_key.startswith('-')
        if not image_queryset.query.standard_ordering:
            # The queryset's reverse() method was called.
            descending = not descending

        field_name = ordering_key.lstrip('-')

        current_image_ordering_value = \
            Image.objects.filter(pk=current_image.pk) \
            .values_list(field_name, flat=True)[0]

        if current_image_ordering_value is None:
            # Nullable fields have a complication: we can't specify
            # `...__gt=None` as a filter kwarg. That gets
            # `ValueError: Cannot use None as a query value`.
            # So instead we'll use the fact that None is ordered after all
            # non-None values. Thus, 'greater than None' means no possible
            # values, and 'less than None' means all non-None values.
            if descending:
                # 'less than None' (all non-None values)
                current_key_after_q = Q(**{field_name + '__isnull': False})
            else:
                # 'greater than None' (always False)
                current_key_after_q = Q(pk__in=[])
        else:
            if descending:
                # 'less than current value'
                current_key_after_q = Q(**{
                    field_name + '__lt': current_image_ordering_value})
            else:
                # 'greater than current value' (greater value or None)
                current_key_after_q = (
                    Q(**{field_name + '__gt': current_image_ordering_value})
                    |
                    Q(**{field_name + '__isnull': True}))

        filter_q = filter_q | (previous_keys_equal_q & current_key_after_q)

        previous_keys_equal_q = previous_keys_equal_q & Q(
            **{field_name: current_image_ordering_value})

    return image_queryset.filter(filter_q)


def get_next_image(current_image, image_queryset, wrap=False):
    """
    Get the next image in the image_queryset, relative to current_image.
    image_queryset should already be ordered, with an unambiguous ordering
    (no ties).

    If wrap is True, then the definition of 'next' is extended to allow
    wrapping from the last image to the first.

    If there is no next image, return None.
    """
    if image_queryset.count() <= 1:
        return None

    next_images = _get_next_images_queryset(current_image, image_queryset)

    if next_images.exists():
        return next_images[0]
    elif wrap:
        # No matching images after this image,
        # so we wrap around to the first image.
        return image_queryset[0]
    else:
        # No matching images after this image, and we're not allowed to wrap.
        return None


def get_prev_image(current_image, image_queryset, wrap=False):
    """
    Get the previous image in the image_queryset, relative to current_image.
    """
    # Finding the previous image is equivalent to
    # finding the next image in the reverse queryset.
    return get_next_image(current_image, image_queryset.reverse(), wrap)


def get_image_order_placement(current_image, image_queryset):
    prev_images = _get_next_images_queryset(
        current_image, image_queryset.reverse())

    # e.g. if there's 4 images that are ordered before the current image,
    # then we return 5
    return prev_images.count() + 1


def metadata_field_names_to_labels(source):
    """
    Get an OrderedDict of Metadata field names to field labels.
    e.g. 'photo_date': "Date", 'aux1': "Site", 'camera': "Camera", ...
    """
    d = OrderedDict(
        (field_name, Metadata._meta.get_field(field_name).verbose_name)
        for field_name
        in Metadata.EDIT_FORM_FIELDS
    )
    # Instead of "Aux1" for field aux1, use the source specified label,
    # e.g. "Site"
    for num, aux_field_name in enumerate(get_aux_field_names(), 1):
        d[aux_field_name] = get_aux_label(source, num)
    return d


def metadata_obj_to_dict(metadata):
    """
    Go from Metadata DB object to metadata dict.
    """
    return dict((k, getattr(metadata, k)) for k in Metadata.EDIT_FORM_FIELDS)


def aux_label_name_collisions(source):
    """
    See if the given source's auxiliary metadata field labels have
    name collisions with (1) built-in metadata fields, or (2) each other.
    Return a list of the names which appear more than once.
    Comparisons are case insensitive.
    """
    field_names_to_labels = metadata_field_names_to_labels(source)
    field_labels_lower = [
        label.lower() for label in field_names_to_labels.values()]

    dupe_labels = [
        label for label in field_labels_lower
        if field_labels_lower.count(label) > 1
    ]
    return dupe_labels


def delete_images(image_queryset):
    """
    Delete Image objects without leaving behind leftover related objects.
    Return the number of Images that were actually deleted.

    We DON'T delete the original image file just yet, because if we did,
    then a subsequent exception in this request/response cycle would leave
    us in an inconsistent state. Leave original image deletion to a
    management command or cronjob.

    It would be reasonable to delete easy-thumbnails' image thumbnails now,
    but best left for later again, for better user-end responsiveness.
    """
    # These are ForeignKey fields of the Image, and thus deleting the Image
    # can't trigger a cascade delete on these objects. So we have to get
    # these objects and delete them separately.
    metadata_queryset = Metadata.objects.filter(image__in=image_queryset)

    # Since these querysets are obtained based on their related images,
    # the querysets will change once the images are deleted!
    # Force-evaluate these querysets BEFORE image deletion.
    # https://docs.djangoproject.com/en/dev/ref/models/querysets/#when-querysets-are-evaluated
    metadata_pks = list(metadata_queryset.values_list('pk', flat=True))
    metadata_queryset = Metadata.objects.filter(pk__in=metadata_pks)

    # We call delete() on the querysets rather than the individual
    # objects for faster performance.
    _, num_objects_deleted = image_queryset.delete()
    delete_count = num_objects_deleted.get('images.Image', 0)

    # We delete the related objects AFTER deleting the images to not trigger
    # PROTECT-related errors on those ForeignKeys.
    metadata_queryset.delete()

    return delete_count


def delete_image(img):
    delete_images(Image.objects.filter(pk=img.pk))


def calculate_points(img,
                     annotation_area=None,
                     point_generation_type=None,
                     simple_number_of_points=None,
                     number_of_cell_rows=None,
                     number_of_cell_columns=None,
                     stratified_points_per_cell=None
):
    """
    Calculate points for this image. This doesn't actually
    insert anything in the database; it just generates the
    row, column for each point number.

    Returns the points as a list of dicts; each dict
    represents a point, and has keys "row", "column",
    and "point_number".
    """

    points = []

    annoarea_min_col = annotation_area['min_x']
    annoarea_max_col = annotation_area['max_x']
    annoarea_min_row = annotation_area['min_y']
    annoarea_max_row = annotation_area['max_y']

    annoarea_height = annoarea_max_row - annoarea_min_row + 1
    annoarea_width = annoarea_max_col - annoarea_min_col + 1


    if point_generation_type == PointGen.Types.SIMPLE:

        simple_random_points = []

        for i in range(simple_number_of_points):
            row = random.randint(annoarea_min_row, annoarea_max_row)
            column = random.randint(annoarea_min_col, annoarea_max_col)

            simple_random_points.append({'row': row, 'column': column})

        # To make consecutive points appear reasonably close to each other, impose cell rows
        # and cols, then make consecutive points fill the cells one by one.
        NUM_OF_CELL_ROWS = 5
        NUM_OF_CELL_COLUMNS = 5
        cell = dict()
        for r in range(NUM_OF_CELL_ROWS):
            cell[r] = dict()
            for c in range(NUM_OF_CELL_COLUMNS):
                cell[r][c] = []

        for p in simple_random_points:
            # Assign each random point to the cell it belongs in.
            # This is all int math, so no floor(), int(), etc. needed.
            # But remember to not divide until the end.
            r = ((p['row'] - annoarea_min_row) * NUM_OF_CELL_ROWS) // annoarea_height
            c = ((p['column'] - annoarea_min_col) * NUM_OF_CELL_COLUMNS) // annoarea_width

            cell[r][c].append(p)

        point_num = 1
        for r in range(NUM_OF_CELL_ROWS):
            for c in range(NUM_OF_CELL_COLUMNS):
                for p in cell[r][c]:

                    points.append(dict(row=p['row'], column=p['column'], point_number=point_num))
                    point_num += 1

    elif point_generation_type == PointGen.Types.STRATIFIED:

        point_num = 1

        # Each pixel of the annotation area goes in exactly one cell.
        # Cell widths and heights are within one pixel of each other.
        for row_num in range(0, number_of_cell_rows):
            row_min = ((row_num * annoarea_height) // number_of_cell_rows) + annoarea_min_row
            row_max = (((row_num+1) * annoarea_height) // number_of_cell_rows) + annoarea_min_row - 1

            for col_num in range(0, number_of_cell_columns):
                col_min = ((col_num * annoarea_width) // number_of_cell_columns) + annoarea_min_col
                col_max = (((col_num+1) * annoarea_width) // number_of_cell_columns) + annoarea_min_col - 1

                for cell_point_num in range(0, stratified_points_per_cell):
                    row = random.randint(row_min, row_max)
                    column = random.randint(col_min, col_max)

                    points.append(dict(row=row, column=column, point_number=point_num))
                    point_num += 1

    elif point_generation_type == PointGen.Types.UNIFORM:

        point_num = 1

        for row_num in range(0, number_of_cell_rows):
            row_min = ((row_num * annoarea_height) // number_of_cell_rows) + annoarea_min_row
            row_max = (((row_num+1) * annoarea_height) // number_of_cell_rows) + annoarea_min_row - 1
            row_mid = (row_min+row_max) // 2

            for col_num in range(0, number_of_cell_columns):
                col_min = ((col_num * annoarea_width) // number_of_cell_columns) + annoarea_min_col
                col_max = (((col_num+1) * annoarea_width) // number_of_cell_columns) + annoarea_min_col - 1
                col_mid = (col_min+col_max) // 2

                points.append(dict(row=row_mid, column=col_mid, point_number=point_num))
                point_num += 1

    return points


def generate_points(img, usesourcemethod=True):
    """
    Generate annotation points for the Image img,
    and delete any points that had previously existed.

    Does nothing if the image already has human annotations,
    because we don't want to delete any human work.
    """

    # If there are any human annotations for this image,
    # abort point generation.
    human_annotations = img.annotation_set.confirmed().exclude(
        user=get_alleviate_user())
    if human_annotations:
        return

    # Find the annotation area, expressed in pixels.
    d = AnnotationAreaUtils.db_format_to_numbers(img.metadata.annotation_area)
    annoarea_type = d.pop('type')
    if annoarea_type == AnnotationAreaUtils.TYPE_PERCENTAGES:
        annoarea_dict = AnnotationAreaUtils.percentages_to_pixels(width=img.original_width, height=img.original_height, **d)
    elif annoarea_type == AnnotationAreaUtils.TYPE_PIXELS:
        annoarea_dict = d
    else:
        raise ValueError("Can't generate points with annotation area type '{0}'.".format(annoarea_type))

    # Calculate points.
    if usesourcemethod:
        point_gen_method = img.source.default_point_generation_method
    else:
        point_gen_method = img.point_generation_method
    
    new_points = calculate_points(
        img, annotation_area=annoarea_dict,
        **PointGen.db_to_args_format(point_gen_method)
    )

    # Delete old points for this image, if any.
    old_points = Point.objects.filter(image=img)
    for old_point in old_points:
        old_point.delete()

    # Any CPC (Coral Point Count file) we had saved previously no longer has
    # the correct point positions, so we'll just discard the CPC.
    img.cpc_content = ''
    img.cpc_filename = ''
    img.save()

    # Save the newly calculated points.
    for new_point in new_points:
        Point(row=new_point['row'],
              column=new_point['column'],
              point_number=new_point['point_number'],
              image=img,
        ).save()


def source_robot_status(source_id):
    """
    checks source with source_id to determine the status of the vision back-end for this source.
    takes: 
    source_id (int)

    gives:
    several data point regarding the status of the vision backend for this source.
    """
    status = dict()
    source = Source.objects.get(id=source_id)
    status['name'] = source.name
    status['name_short'] = source.name[:40]
    status['id'] = source.id
    status['has_robot'] = source.has_robot()
    status['nbr_robots'] = source.classifier_set.count()
    status['nbr_accepted_robots'] = source.get_accepted_robots().count()

    status['nbr_total_images'] = Image.objects.filter(source=source).count()
    status['nbr_images_needs_features'] = Image.objects.filter(source=source, features__extracted=False).count()
    status['nbr_unclassified_images'] = Image.objects.filter(source=source, features__classified=False, annoinfo__confirmed=False).count()
    status['nbr_human_annotated_images'] = Image.objects.filter(source=source, annoinfo__confirmed=True).count()

    status['nbr_in_current_model'] = (
        source.get_current_classifier().nbr_train_images
        if status['has_robot'] else 0)
    if source.has_robot():
        status['nbr_images_until_next_robot'] = status['nbr_in_current_model'] * settings.NEW_CLASSIFIER_TRAIN_TH - status['nbr_human_annotated_images']
    else:
        status['nbr_images_until_next_robot'] = settings.MIN_NBR_ANNOTATED_IMAGES - status['nbr_human_annotated_images']
    status['nbr_images_until_next_robot'] = int(math.ceil(status['nbr_images_until_next_robot']))

    status['need_robot'], _ = source.need_new_robot()
    status['need_features'] = status['nbr_images_needs_features'] > 0
    status['need_classification'] = status['has_robot'] and status['nbr_unclassified_images'] > 0

    status['need_attention'] = source.enable_robot_classifier and (status['need_robot'] or status['need_features'] or status['need_classification'])

    return status


def filter_out_test_sources(source_queryset):
    for possible_test_substring in settings.LIKELY_TEST_SOURCE_NAMES:
        source_queryset = source_queryset.exclude(name__icontains=possible_test_substring)
    return source_queryset


def get_map_sources():
    # Get all sources that have both latitude and longitude specified.
    # (In other words, leave out the sources that have either of them blank.)
    map_sources_qs = Source.objects.exclude(latitude='').exclude(longitude='')
    # Skip test sources.
    map_sources_qs = filter_out_test_sources(map_sources_qs)
    # Skip small sources.
    map_sources_qs = map_sources_qs.annotate(image_count=Count('image'))
    map_sources_qs = map_sources_qs.exclude(
        image_count__lt=settings.MAP_IMAGE_COUNT_TIERS[0])

    map_sources = []

    for source in map_sources_qs:
        if source.is_public():
            source_type = 'public'
        else:
            source_type = 'private'

        if source.image_count < settings.MAP_IMAGE_COUNT_TIERS[1]:
            size = 1
        elif source.image_count < settings.MAP_IMAGE_COUNT_TIERS[2]:
            size = 2
        else:
            size = 3

        map_sources.append(dict(
            sourceId=source.id,
            latitude=source.latitude,
            longitude=source.longitude,
            type=source_type,
            size=size,
            detailBoxUrl=reverse('source_detail_box', args=[source.id]),
        ))

    return map_sources


def get_carousel_images():
    """
    Get images for the front page carousel.

    We randomly pick <image_count> images out of a pool. The pool is specified
    in settings, and should be hand-picked from public sources.
    """
    image_count = settings.CAROUSEL_IMAGE_COUNT
    image_pks = random.sample(settings.CAROUSEL_IMAGE_POOL, image_count)
    return Image.objects.filter(pk__in=image_pks)


# Functions to encapsulate the auxiliary metadata
# field details.

def get_aux_label_field_name(aux_field_number):
    return 'key'+str(aux_field_number)
def get_aux_field_name(aux_field_number):
    return 'aux'+str(aux_field_number)

def get_aux_label(source, aux_field_number):
    return getattr(source, get_aux_label_field_name(aux_field_number))

def get_num_aux_fields():
    return 5

def get_aux_label_field_names():
    return [
        get_aux_label_field_name(n)
        for n in range(1, get_num_aux_fields()+1)]

def get_aux_field_names():
    return [
        get_aux_field_name(n)
        for n in range(1, get_num_aux_fields()+1)]

def get_aux_labels(source):
    return [
        get_aux_label(source, aux_field_number)
        for aux_field_number in range(1, get_num_aux_fields()+1)]

def get_aux_metadata_form_choices(source, aux_field_number):
    # On using distinct(): http://stackoverflow.com/a/2468620/
    distinct_aux_values = Metadata.objects.filter(image__source=source) \
        .values_list(get_aux_field_name(aux_field_number), flat=True) \
        .distinct()
    return [(v,v) for v in distinct_aux_values if v != '']

def get_aux_metadata_db_value_dict_from_str_list(source, str_list):
    aux_dict = dict()
    for aux_field_number, s in enumerate(str_list, 1):
        aux_field_name = get_aux_field_name(aux_field_number)
        aux_dict[aux_field_name] = s
    return aux_dict

def get_aux_metadata_str_for_image(image, aux_field_number):
    return getattr(image.metadata, get_aux_field_name(aux_field_number))

def get_aux_metadata_max_length():
    # This assumes all aux metadata fields have the same max length.
    # Assuming the user can't customize it, they should be the same.
    return Metadata._meta.get_field(
        get_aux_field_name(1)).max_length

def update_filter_args_specifying_aux_metadata(
        filter_args, aux_field_number, value):
    filter_args['metadata__'+get_aux_field_name(aux_field_number)] = value


# Other auxiliary metadata related functions.
# TODO: These could go in model Manager classes.

def get_aux_metadata_str_list_for_image(image, for_export=False):
    lst = []
    for n in range(1, get_num_aux_fields()+1):
        s = get_aux_metadata_str_for_image(image, n)
        if for_export and s == '':
            s = "not specified"
        lst.append(s)

    return lst

def get_date_and_aux_metadata_table(image):
    """
    Get the year and aux metadata for display as a 2 x n table.
    """
    cols = []

    if image.metadata.photo_date:
        date_str = datetime.datetime.strftime(
            image.metadata.photo_date, "%Y-%m-%d")
    else:
        date_str = "-"
    cols.append(("Date", date_str))

    for n in range(1, get_num_aux_fields()+1):
        aux_label = get_aux_label(image.source, n)
        aux_value = get_aux_metadata_str_for_image(image, n)
        if aux_value == "":
            aux_value = "-"
        cols.append((aux_label, aux_value))

    # Transpose
    rows = dict(
        keys=[c[0] for c in cols],
        values=[c[1] for c in cols],
    )
    return rows
