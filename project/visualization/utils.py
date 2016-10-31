from io import BytesIO
from django.conf import settings
from django.core.files.storage import get_storage_class
import django.db.models.fields as model_fields
from PIL import Image as PILImage
from images.models import Point, Image, Metadata


def image_search_kwargs_to_queryset(search_kwargs, source):
    queryset_kwargs = dict()

    # Date
    date_filter_kwargs = search_kwargs.get('date_filter', None)
    if date_filter_kwargs:
        queryset_kwargs.update(date_filter_kwargs)

    # Metadata fields
    metadata_field_names = [
        'aux1', 'aux2', 'aux3', 'aux4', 'aux5',
        'height_in_cm', 'latitude', 'longitude', 'depth',
        'camera', 'photographer', 'water_quality',
        'strobes', 'framing', 'balance',
    ]
    for field_name in metadata_field_names:
        value = search_kwargs.get(field_name, '')
        if value == '':
            # Don't filter by this field
            pass
        elif value == '(none)':
            # Get images with an empty value for this field
            if isinstance(
              Metadata._meta.get_field(field_name), model_fields.CharField):
                queryset_kwargs['metadata__' + field_name] = ''
            else:
                queryset_kwargs['metadata__' + field_name] = None
        else:
            # Filter by the given non-empty value
            queryset_kwargs['metadata__' + field_name] = value

    # Annotation status
    annotation_status = search_kwargs.get('annotation_status', '')
    if annotation_status == '':
        # Don't filter
        pass
    elif annotation_status == 'confirmed':
        queryset_kwargs['confirmed'] = True
    elif annotation_status == 'unconfirmed':
        queryset_kwargs['confirmed'] = False
        queryset_kwargs['features__classified'] = True
    elif annotation_status == 'unclassified':
        queryset_kwargs['confirmed'] = False
        queryset_kwargs['features__classified'] = False

    image_results = Image.objects.filter(source=source, **queryset_kwargs)

    return image_results


def get_patch_path(point_id):
    point = Point.objects.get(pk=point_id)

    return settings.POINT_PATCH_FILE_PATTERN.format(
        full_image_path=point.image.original_file.name,
        point_pk=point.pk,
    )

def get_patch_url(point_id):
    return get_storage_class()().url(get_patch_path(point_id))

def generate_patch_if_doesnt_exist(point):
    """
    If this point doesn't have an image patch file yet, then
    generate one.
    :param point: Point object to generate a patch for
    :return: None
    """
    # Get the storage class, then get an instance of it.
    storage = get_storage_class()()
    # Check if patch exists for the point
    patch_relative_path = get_patch_path(point.pk)
    if storage.exists(patch_relative_path):
        return

    # Generate the patch

    # Size of patch (after scaling)
    PATCH_X = 150
    PATCH_Y = 150
    # Patch covers this proportion of the original image's greater dimension
    REDUCE_SIZE = 1.0/5.0

    original_image_relative_path = point.image.original_file.name
    original_image_file = storage.open(original_image_relative_path)
    image = PILImage.open(original_image_file)

    #determine the crop box
    max_x = point.image.original_width
    max_y = point.image.original_height
    #careful; x is the column, y is the row
    x = point.column
    y = point.row

    # TODO: The division ops here MIGHT be dangerous for Python 3, because
    # the default has changed from integer to decimal division
    patchSize = int(max(max_x,max_y)*REDUCE_SIZE)
    patchSize = (patchSize/2)*2  #force patch size to be even
    halfPatchSize = patchSize/2
    scaledPatchSize = (PATCH_X, PATCH_Y)

    # If a patch centered on (x,y) would be too far off to the left,
    # then just take a patch on the left edge of the image.
    if x - halfPatchSize < 0:
        left = 0
        right = patchSize
    # If too far to the right, take a patch on the right edge
    elif x + halfPatchSize > max_x:
        left = max_x - patchSize
        right = max_x
    else:
        left = x - halfPatchSize
        right = x + halfPatchSize

    # If too far toward the top, take a patch on the top edge
    if y - halfPatchSize < 0:
        upper = 0
        lower = patchSize
    # If too far toward the bottom, take a patch on the bottom edge
    elif y + halfPatchSize > max_y:
        upper = max_y - patchSize
        lower = max_y
    else:
        upper = y - halfPatchSize
        lower = y + halfPatchSize

    box = (left,upper,right,lower)

    # Crop the image
    region = image.crop(box)
    region = region.resize(scaledPatchSize)

    # Save the image.
    #
    # First use Pillow's save() method on an IO stream (so we don't have to
    # create a temporary file).
    # Then save the image, using the path constructed earlier and the
    # contents of the stream.
    # This approach should work with both local and remote storage.
    with BytesIO() as stream:
        region.save(stream, 'JPEG')
        storage.save(patch_relative_path, stream)