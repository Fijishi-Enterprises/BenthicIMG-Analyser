import math, random

from django.conf import settings
from django.core.urlresolvers import reverse

from accounts.utils import get_robot_user, get_alleviate_user
from annotations.model_utils import AnnotationAreaUtils
from annotations.models import Annotation
from images.model_utils import PointGen
from images.models import Source, Point, Image, Value1, Value2, Value3, Value4, Value5


def get_first_image(source, conditions=None):
    """
    Gets the first image in the source.
    Ordering is done by image id.

    conditions:
    A dict specifying additional filters.
    """
    imgs = Image.objects.filter(source=source)

    if conditions:
        filter_kwargs = dict()
        for key, value in conditions.iteritems():
            filter_kwargs[key] = value
        imgs = imgs.filter(**filter_kwargs)

    if not imgs:
        return None

    imgs_ordered = imgs.order_by('pk')

    return imgs_ordered[0]


def get_prev_or_next_image(current_image, kind, conditions=None):
    """
    Gets the previous or next image in this image's source.

    conditions:
    A list specifying additional filters. For example, 'needs_human_annotation'.
    """
    imgs = Image.objects.filter(source=current_image.source)

    if conditions:
        filter_kwargs = dict()
        for key, value in conditions.iteritems():
            filter_kwargs[key] = value
        imgs = imgs.filter(**filter_kwargs)

    if kind == 'prev':
        # Order imgs so that highest pk comes first.
        # Then keep only the imgs with pk less than this image.
        imgs_ordered = imgs.order_by('-pk')
        candidate_imgs = imgs_ordered.filter(pk__lt=current_image.pk)
    else: # next
        # Order imgs so that lowest pk comes first.
        # Then keep only the imgs with pk greater than this image.
        imgs_ordered = imgs.order_by('pk')
        candidate_imgs = imgs_ordered.filter(pk__gt=current_image.pk)

    if candidate_imgs:
        return candidate_imgs[0]
    else:
        # No matching images before this image (if requesting prev) or
        # after this image (if requesting next).
        return None


def get_next_image(current_image, conditions=None):
    """
    Get the "next" image in the source.
    Return None if the current image is the last image.
    """
    return get_prev_or_next_image(current_image, 'next', conditions=conditions)

def get_prev_image(current_image, conditions=None):
    """
    Get the "previous" image in the source.
    Return None if the current image is the first image.
    """
    return get_prev_or_next_image(current_image, 'prev', conditions=conditions)


def delete_image(img):
    """
    Delete an Image object without leaving behind leftover related objects.

    We DON'T delete the original image file just yet, because if we did,
    then a subsequent exception in this request/response cycle would leave
    us in an inconsistent state. Leave original image deletion to a
    management command or cronjob.

    We do delete easy-thumbnails' image thumbnails though.
    Unlike the original image, these thumbnails can be re-generated at
    any time, so it's no big deal if we get an exception later.

    :param img: The Image object to delete.
    :param delete_files: True to delete the associated image files from
    the filesystem.
    :return: None.
    """
    # Delete easy-thumbnails-generated thumbnail files.
    # This is easier to do while the image still exists, so we can
    # just call delete_thumbnails().
    img.original_file.delete_thumbnails()

    # These are ForeignKey fields of the Image, and thus deleting the Image
    # can't trigger a cascade delete on these objects. So we have to get
    # these objects and delete them separately. Also, we delete them after
    # deleting the image to not trigger PROTECT-related errors on those
    # ForeignKeys.
    metadata = img.metadata
    status = img.status

    img.delete()
    metadata.delete()
    status.delete()


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
            r = ((p['row'] - annoarea_min_row) * NUM_OF_CELL_ROWS) / annoarea_height
            c = ((p['column'] - annoarea_min_col) * NUM_OF_CELL_COLUMNS) / annoarea_width

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
            row_min = ((row_num * annoarea_height) / number_of_cell_rows) + annoarea_min_row
            row_max = (((row_num+1) * annoarea_height) / number_of_cell_rows) + annoarea_min_row - 1

            for col_num in range(0, number_of_cell_columns):
                col_min = ((col_num * annoarea_width) / number_of_cell_columns) + annoarea_min_col
                col_max = (((col_num+1) * annoarea_width) / number_of_cell_columns) + annoarea_min_col - 1

                for cell_point_num in range(0, stratified_points_per_cell):
                    row = random.randint(row_min, row_max)
                    column = random.randint(col_min, col_max)

                    points.append(dict(row=row, column=column, point_number=point_num))
                    point_num += 1

    elif point_generation_type == PointGen.Types.UNIFORM:

        point_num = 1

        for row_num in range(0, number_of_cell_rows):
            row_min = ((row_num * annoarea_height) / number_of_cell_rows) + annoarea_min_row
            row_max = (((row_num+1) * annoarea_height) / number_of_cell_rows) + annoarea_min_row - 1
            row_mid = int(math.floor( (row_min+row_max) / 2.0 ))

            for col_num in range(0, number_of_cell_columns):
                col_min = ((col_num * annoarea_width) / number_of_cell_columns) + annoarea_min_col
                col_max = (((col_num+1) * annoarea_width) / number_of_cell_columns) + annoarea_min_col - 1
                col_mid = int(math.floor( (col_min+col_max) / 2.0 ))

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
    human_annotations = Annotation.objects.filter(image = img).exclude(user = get_robot_user()).exclude(user = get_alleviate_user())
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

    # Save the newly calculated points.
    for new_point in new_points:
        Point(row=new_point['row'],
              column=new_point['column'],
              point_number=new_point['point_number'],
              image=img,
        ).save()

    # Update image status.
    # Make sure the image goes through the feature-making step again.
    status = img.status
    status.hasRandomPoints = True
    status.save()


def source_robot_status(source_id):
    """
    checks source with source_id to determine the status of the vision back-end for this source.
    takes: 
    source_id (int)

    gives:
    several data point regarding the status of the vision backend for this source.
    """
    status = dict()
    source = Source.objects.get(id = source_id)
    status['name'] = source.name
    status['name_short'] = source.name[:40]
    status['id'] = source.id
    status['has_robot'] = source.get_latest_robot() is not None
    status['nbr_total_images'] = Image.objects.filter(source=source).count()
    status['nbr_images_needs_features'] = Image.objects.filter(source=source, status__featuresExtracted=False).count()
    status['nbr_unclassified_images'] = Image.objects.filter(source=source, status__annotatedByRobot=False, status__annotatedByHuman=False).count()
    
    
    status['nbr_human_annotated_images'] = Image.objects.filter(source=source, status__annotatedByHuman = True).count()
    status['nbr_in_current_model'] = Image.objects.filter(source=source, status__usedInCurrentModel = True).count()
    if source.has_robot():
        status['nbr_images_until_next_robot'] = status['nbr_in_current_model'] * settings.NEW_MODEL_THRESHOLD - status['nbr_human_annotated_images']
    else:
        status['nbr_images_until_next_robot'] = settings.MIN_NBR_ANNOTATED_IMAGES - status['nbr_human_annotated_images']
    status['nbr_images_until_next_robot'] = int(math.ceil(status['nbr_images_until_next_robot']))

    status['need_robot'] = source.need_new_robot()
    status['need_features'] = status['nbr_images_needs_features'] > 0
    status['need_classification'] = status['has_robot'] and status['nbr_unclassified_images'] > 0

    status['need_attention'] = source.enable_robot_classifier and (status['need_robot'] or status['need_features'] or status['need_classification'])

    return status


def get_map_sources():
    # Get all sources that have both latitude and longitude specified.
    # (In other words, leave out the sources that have either of them blank.)
    map_sources_queryset = Source.objects.exclude(latitude='').exclude(longitude='')

    map_sources = []

    for source in map_sources_queryset:

        num_of_images = Image.objects.filter(source=source).count()

        # Make some check to remove small sources and test sources
        is_test_source = False
        if num_of_images < 100:
            continue
        possible_test_sources_substrings = ['test', 'sandbox', 'dummy', 'tmp', 'temp', 'check']
        for str_ in possible_test_sources_substrings:
            if str_ in source.name.lower():
                continue

        # If the source is public, include a link to the source main page.
        # Otherwise, don't include a link.
        if source.visibility == Source.VisibilityTypes.PUBLIC:
            source_url = reverse('source_main', args=[source.id])
            color = '00FF00'
        else:
            source_url = ''
            color = 'FF0000'

        try:
            latitude = str(source.latitude)
            longitude = str(source.longitude)
        except:
            latitude = 'invalid'
            longitude = 'invalid'

        all_images = source.get_all_images()
        latest_images = all_images.order_by('-upload_date')[:6]

        map_sources.append(dict(
            description=source.description,
            affiliation=source.affiliation,
            latitude=latitude,
            longitude=longitude,
            name=source.name,
            color = color,
            num_of_images=str( num_of_images ),
            url=source_url,
            latest_images=latest_images,
            id=source.id
        ))

    return map_sources


def get_random_public_images():
    """
    This will return a list of 5 random images that are from public sources only.
    These will be displayed on the front page to be seen in all their glory
    """
    public_sources_list = Source.get_public_sources()

    # return empty list if no public sources
    if len(public_sources_list) == 0:
        return public_sources_list

    random_source_list = []
    random_image_list = []

    # get 5 random public sources
    for i in range(5):
        random_source = random.choice(public_sources_list)
        random_source_list.append(random_source)

    # get a random image from each randomly chosen public source
    for source in random_source_list:
        all_images = source.get_all_images()

        if len(all_images) == 0:
            continue

        random_image = random.choice(all_images)
        random_image_list.append(random_image)

    return random_image_list


# Functions to encapsulate the auxiliary metadata / location value
# field details.

def get_aux_metadata_class(aux_field_number):
    """
    This function shouldn't be used outside of this utils module. It's
    tied to the detail of having classes for aux metadata.
    """
    numbers_to_classes = {
        1: Value1, 2: Value2, 3: Value3, 4: Value4, 5: Value5}
    return numbers_to_classes[aux_field_number]

def get_aux_label_field_name(aux_field_number):
    return 'key'+str(aux_field_number)
def get_aux_field_name(aux_field_number):
    return 'value'+str(aux_field_number)

def get_all_aux_field_names():
    return [get_aux_field_name(n) for n in range(1, 5+1)]

def get_aux_label(source, aux_field_number):
    return getattr(source, get_aux_label_field_name(aux_field_number))

def get_num_aux_fields(source):
    """
    If assuming all 5 aux fields are always used,
    replace calls with:
    5
    (Or a constant equal to 5)
    """
    NUM_AUX_FIELDS = 5
    for n in range(1, NUM_AUX_FIELDS+1):
        aux_label = get_aux_label(source, n)
        if not aux_label:
            return n-1
    return NUM_AUX_FIELDS

def get_aux_label_field_names(source):
    """
    If assuming all 5 aux fields are always used,
    replace calls with:
    [get_aux_label_field_name(n) for n in range(1, 5+1)]
    """
    return [
        get_aux_label_field_name(n)
        for n in range(1, get_num_aux_fields(source)+1)]

def get_aux_field_names(source):
    """
    If assuming all 5 aux fields are always used,
    replace calls with:
    [get_aux_field_name(n) for n in range(1, 5+1)]
    """
    return [
        get_aux_field_name(n)
        for n in range(1, get_num_aux_fields(source)+1)]

def get_aux_labels(source):
    return [
        get_aux_label(source, aux_field_number)
        for aux_field_number in range(1, get_num_aux_fields(source)+1)]

def get_aux_metadata_form_choices(source, aux_field_number):
    """
    When aux metadata are just simple string fields,
    replace calls with:
    Metadata.objects.filter(image__source__pk=10) \
    .distinct(get_aux_field_name(aux_field_number)) \
    .values_list(get_aux_field_name(aux_field_number), flat=True)

    ...Or better, keep this function and replace the implementation with that.
    """
    aux_metadata_class = get_aux_metadata_class(aux_field_number)

    aux_metadata_objs = aux_metadata_class.objects.filter(source=source) \
        .order_by('name')
    return [(obj.id, obj.name) for obj in aux_metadata_objs]

def get_aux_metadata_db_value_from_form_choice(aux_field_number, choice):
    """
    When aux metadata are just simple string fields,
    replace calls with:
    choice
    """
    if choice == '':
        return None
    aux_metadata_class = get_aux_metadata_class(aux_field_number)
    return aux_metadata_class.objects.get(pk=choice)

def get_aux_metadata_db_value_from_str(source, aux_field_number, s):
    """
    When aux metadata are just simple string fields,
    replace calls with:
    s
    """
    if s == '':
        return None
    aux_metadata_class = get_aux_metadata_class(aux_field_number)
    obj, created = aux_metadata_class.objects.get_or_create(
        name=s, source=source)
    return obj

def get_aux_metadata_db_value_dict_from_str_list(source, str_list):
    """
    When aux metadata are just simple string fields,
    can replace with:
    aux_dict = dict()
    for aux_field_number, s in enumerate(str_list, 1):
        aux_field_name = get_aux_field_name(aux_field_number)
        aux_dict[aux_field_name] = s
    return aux_dict

    But this functionality might just not be needed at that point.
    """
    aux_dict = dict()
    for aux_field_number, s in enumerate(str_list, 1):
        aux_field_name = get_aux_field_name(aux_field_number)
        aux_metadata_class = get_aux_metadata_class(aux_field_number)
        if s == '':
            aux_dict[aux_field_name] = None
        else:
            aux_dict[aux_field_name], created = aux_metadata_class.objects.get_or_create(
                name=s, source=source)
    return aux_dict

def get_aux_metadata_post_form_value_from_str(source, aux_field_number, s):
    """
    When aux metadata are just simple string fields,
    replace calls with:
    s
    """
    if s == '':
        return None
    aux_metadata_class = get_aux_metadata_class(aux_field_number)
    obj, created = aux_metadata_class.objects.get_or_create(
        name=s, source=source)
    return obj.pk

def get_aux_metadata_str_for_image(image, aux_field_number):
    """
    When aux metadata are just simple string fields,
    replace calls with:
    getattr(image.metadata, get_aux_field_name(aux_field_number))
    """
    obj = getattr(image.metadata, get_aux_field_name(aux_field_number))
    if obj:
        return obj.name
    return ''

def get_aux_metadata_max_length(aux_field_number):
    """
    When aux metadata are just simple string fields,
    replace calls with:
    Source._meta.get_field(get_aux_field_name(aux_field_number)).max_length
    """
    aux_metadata_class = get_aux_metadata_class(aux_field_number)
    return aux_metadata_class._meta.get_field('name').max_length

def get_aux_metadata_valid_db_value(aux_field_number):
    """
    When aux metadata are just simple string fields,
    this probably won't ever be needed.

    Warning: This may get an exception if there are no objects of
    aux_metadata_class on the site yet. (e.g. no Value5s)
    """
    aux_metadata_class = get_aux_metadata_class(aux_field_number)
    return aux_metadata_class.objects.all()[0]

def update_filter_args_specifying_blank_aux_metadata(
        filter_args, aux_field_number):
    """
    When aux metadata are just simple string fields,
    replace calls with:
    filter_args['metadata__'+get_aux_field_name(aux_field_number)] = ''
    """
    filter_args['metadata__'+get_aux_field_name(aux_field_number)] = None

def update_filter_args_specifying_choice_aux_metadata(
        filter_args, aux_field_number, value):
    """
    When aux metadata are just simple string fields,
    replace calls with:
    filter_args['metadata__'+get_aux_field_name(aux_field_number)] = value

    A dropdown choice of aux metadata should be an id if
    values have model classes, and should be a string otherwise.
    """
    filter_args['metadata__'+get_aux_field_name(aux_field_number)+'__id'] \
        = value


# Other auxiliary metadata related functions.
# TODO: These could go in model Manager classes.

def get_aux_metadata_str_list_for_image(image, for_export=False):
    lst = []
    for n in range(1, get_num_aux_fields(image.source)+1):
        s = get_aux_metadata_str_for_image(image, n)
        if for_export and s == '':
            s = "not specified"
        lst.append(s)

    return lst

def get_year_and_aux_metadata_table(image):
    """
    Get the year and aux metadata for display as a 2 x n table.
    """
    cols = []

    if image.metadata.photo_date:
        cols.append( ("Year", str(image.metadata.photo_date.year)) )
    else:
        cols.append( ("Year", "") )

    for n in range(1, get_num_aux_fields(image.source)+1):
        aux_label = get_aux_label(image.source, n)
        cols.append(
            (aux_label, get_aux_metadata_str_for_image(image, n)))

    # Transpose
    rows = dict(
        keys=[c[0] for c in cols],
        values=[c[1] for c in cols],
    )
    return rows