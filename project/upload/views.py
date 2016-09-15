import json

from django.conf import settings
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404, render

from accounts.utils import get_imported_user
from annotations.model_utils import AnnotationAreaUtils
from annotations.models import Annotation
from images.forms import MetadataForm
from images.model_utils import PointGen
from images.models import Source, Metadata, Image, Point
from images.utils import metadata_obj_to_dict, get_aux_labels, \
    metadata_field_names_to_labels
from lib.decorators import source_permission_required
from lib.exceptions import FileProcessError
from lib.utils import filesize_display
from visualization.forms import ImageSpecifyByIdForm
from .forms import MultiImageUploadForm, ImageUploadForm, CSVImportForm
from .utils import upload_image_process, find_dupe_image,\
    metadata_csv_to_dict, annotations_csv_to_dict, \
    annotations_preview, metadata_preview


@source_permission_required('source_id', perm=Source.PermTypes.EDIT.code)
def upload_portal(request, source_id):
    """
    Page which points to the pages for the three different upload types.
    """
    if request.method == 'POST':
        if request.POST.get('images'):
            return HttpResponseRedirect(
                reverse('upload_images', args=[source_id]))
        if request.POST.get('metadata'):
            return HttpResponseRedirect(
                reverse('upload_metadata', args=[source_id]))
        if request.POST.get('annotations'):
            return HttpResponseRedirect(
                reverse('upload_annotations', args=[source_id]))

    source = get_object_or_404(Source, id=source_id)
    return render(request, 'upload/upload_portal.html', {
        'source': source,
    })


@source_permission_required('source_id', perm=Source.PermTypes.EDIT.code)
def upload_images(request, source_id):
    """
    Upload images to a source.
    This view is for the non-Ajax frontend.
    """
    source = get_object_or_404(Source, id=source_id)

    images_form = MultiImageUploadForm()
    proceed_to_manage_metadata_form = ImageSpecifyByIdForm(source=source)

    auto_generate_points_message = (
        "We will generate points for the images you upload.\n"
        "Your Source's point generation settings: {pointgen}\n"
        "Your Source's annotation area settings: {annoarea}").format(
            pointgen=PointGen.db_to_readable_format(
                source.default_point_generation_method),
            annoarea=AnnotationAreaUtils.db_format_to_display(
                source.image_annotation_area),
        )

    return render(request, 'upload/upload_images.html', {
        'source': source,
        'images_form': images_form,
        'proceed_to_manage_metadata_form': proceed_to_manage_metadata_form,
        'auto_generate_points_message': auto_generate_points_message,
        'image_upload_max_file_size': filesize_display(
            settings.IMAGE_UPLOAD_MAX_FILE_SIZE),
    })


@source_permission_required(
    'source_id', perm=Source.PermTypes.EDIT.code, ajax=True)
def upload_images_preview_ajax(request, source_id):
    """
    Preview the images that are about to be uploaded.
    Check to see if there's any problems with the filenames or file sizes.
    """
    if request.method != 'POST':
        return JsonResponse(dict(
            error="Not a POST request",
        ))

    source = get_object_or_404(Source, id=source_id)

    file_info_list = json.loads(request.POST.get('file_info'))

    statuses = []

    for file_info in file_info_list:

        dupe_image = find_dupe_image(source, file_info['filename'])
        if dupe_image:
            statuses.append(dict(
                error="Image with this name already exists",
                url=reverse('image_detail', args=[dupe_image.id]),
            ))
        elif file_info['size'] > settings.IMAGE_UPLOAD_MAX_FILE_SIZE:
            statuses.append(dict(
                error="Exceeds size limit of {limit}".format(
                    limit=filesize_display(
                        settings.IMAGE_UPLOAD_MAX_FILE_SIZE))
            ))
        else:
            statuses.append(dict(
                ok=True,
            ))

    return JsonResponse(dict(
        statuses=statuses,
    ))


@source_permission_required(
    'source_id', perm=Source.PermTypes.EDIT.code, ajax=True)
def upload_images_ajax(request, source_id):
    """
    After the "Start upload" button is clicked, this view is entered once
    for each image file. This view saves the image to the database
    and media storage.
    """
    if request.method != 'POST':
        return JsonResponse(dict(
            error="Not a POST request",
        ))

    source = get_object_or_404(Source, id=source_id)

    # Retrieve image related fields
    image_form = ImageUploadForm(request.POST, request.FILES)

    # Check for validity of the file (filetype and non-corruptness) and
    # the options forms.
    if not image_form.is_valid():
        # File error: filetype is not an image,
        # file is corrupt, file is empty, etc.
        return JsonResponse(dict(
            error=image_form.errors['file'][0],
        ))

    img = upload_image_process(
        imageFile=image_form.cleaned_data['file'],
        source=source,
        currentUser=request.user,
    )

    return JsonResponse(dict(
        success=True,
        link=reverse('image_detail', args=[img.id]),
        image_id=img.id,
    ))


@source_permission_required('source_id', perm=Source.PermTypes.EDIT.code)
def upload_metadata(request, source_id):
    """
    Set image metadata by uploading a CSV file containing the metadata.
    This view is for the non-Ajax frontend.
    """
    source = get_object_or_404(Source, id=source_id)

    csv_import_form = CSVImportForm()

    return render(request, 'upload/upload_metadata.html', {
        'source': source,
        'csv_import_form': csv_import_form,
        'field_labels': metadata_field_names_to_labels(source).values(),
        'aux_field_labels': get_aux_labels(source),
    })


@source_permission_required(
    'source_id', perm=Source.PermTypes.EDIT.code, ajax=True)
def upload_metadata_preview_ajax(request, source_id):
    """
    Set image metadata by uploading a CSV file containing the metadata.

    This view takes the CSV file, processes it, saves the processed metadata
    to the session, and returns a preview table of the metadata to be saved.
    """
    if request.method != 'POST':
        return JsonResponse(dict(
            error="Not a POST request",
        ))

    source = get_object_or_404(Source, id=source_id)

    csv_import_form = CSVImportForm(request.POST, request.FILES)
    if not csv_import_form.is_valid():
        return JsonResponse(dict(
            error=csv_import_form.errors['csv_file'][0],
        ))

    try:
        # Dict of (metadata ids -> dicts of (column name -> value))
        csv_metadata = metadata_csv_to_dict(
            csv_import_form.cleaned_data['csv_file'], source)
    except FileProcessError as error:
        return JsonResponse(dict(
            error=error.message,
         ))

    preview_table, preview_details = \
        metadata_preview(csv_metadata, source)

    request.session['csv_metadata'] = csv_metadata

    return JsonResponse(dict(
        success=True,
        previewTable=preview_table,
        previewDetails=preview_details,
    ))


@source_permission_required(
    'source_id', perm=Source.PermTypes.EDIT.code, ajax=True)
def upload_metadata_ajax(request, source_id):
    """
    Set image metadata by uploading a CSV file containing the metadata.

    This view gets the metadata that was previously saved to the session
    by the upload-preview view. Then it saves the metadata to the database.
    """
    if request.method != 'POST':
        return JsonResponse(dict(
            error="Not a POST request",
        ))

    source = get_object_or_404(Source, id=source_id)

    csv_metadata = request.session.pop('csv_metadata')
    if not csv_metadata:
        return JsonResponse(dict(
            error=(
                "We couldn't find the expected data in your session."
                " Please try loading this page again. If the problem persists,"
                " contact a site admin."
            ),
        ))

    for metadata_id, csv_metadata_for_image in csv_metadata.items():

        metadata = Metadata.objects.get(pk=metadata_id, image__source=source)
        new_metadata_dict = metadata_obj_to_dict(metadata)
        new_metadata_dict.update(csv_metadata_for_image)

        metadata_form = MetadataForm(
            new_metadata_dict, instance=metadata, source=source)

        # We already validated previously, so this SHOULD be valid.
        if not metadata_form.is_valid():
            raise ValueError("Metadata became invalid for some reason.")

        metadata_form.save()

    return JsonResponse(dict(
        success=True,
    ))


@source_permission_required('source_id', perm=Source.PermTypes.EDIT.code)
def upload_annotations(request, source_id):
    source = get_object_or_404(Source, id=source_id)

    csv_import_form = CSVImportForm()

    return render(request, 'upload/upload_annotations.html', {
        'source': source,
        'csv_import_form': csv_import_form,
    })


@source_permission_required(
    'source_id', perm=Source.PermTypes.EDIT.code, ajax=True)
def upload_annotations_preview_ajax(request, source_id):
    """
    Add points/annotations to images by uploading a CSV file.

    This view takes the CSV file, processes it, saves the processed data
    to the session, and returns a preview table of the data to be saved.
    """
    if request.method != 'POST':
        return JsonResponse(dict(
            error="Not a POST request",
        ))

    source = get_object_or_404(Source, id=source_id)

    csv_import_form = CSVImportForm(request.POST, request.FILES)
    if not csv_import_form.is_valid():
        return JsonResponse(dict(
            error=csv_import_form.errors['csv_file'][0],
        ))

    try:
        csv_annotations = annotations_csv_to_dict(
            csv_import_form.cleaned_data['csv_file'], source)
    except FileProcessError as error:
        return JsonResponse(dict(
            error=error.message,
        ))

    preview_table, preview_details = \
        annotations_preview(csv_annotations, source)

    request.session['csv_annotations'] = csv_annotations

    return JsonResponse(dict(
        success=True,
        previewTable=preview_table,
        previewDetails=preview_details,
    ))


@source_permission_required(
    'source_id', perm=Source.PermTypes.EDIT.code, ajax=True)
def upload_annotations_ajax(request, source_id):
    """
    Add points/annotations to images by uploading a CSV file.

    This view gets the data that was previously saved to the session
    by the upload-preview view. Then it saves the data to the database,
    while deleting all previous points/annotations for the images involved.
    """
    if request.method != 'POST':
        return JsonResponse(dict(
            error="Not a POST request",
        ))

    source = get_object_or_404(Source, id=source_id)

    csv_annotations = request.session.pop('csv_annotations')
    if not csv_annotations:
        return JsonResponse(dict(
            error=(
                "We couldn't find the expected data in your session."
                " Please try loading this page again. If the problem persists,"
                " contact a site admin."
            ),
        ))

    for image_id, csv_annotations_for_image in csv_annotations.items():

        img = Image.objects.get(pk=image_id, source=source)

        # Delete previous annotations and points for this image.
        # Calling delete() on these querysets is more efficient
        # than calling delete() on each of the individual objects.
        Annotation.objects.filter(image=img).delete()
        Point.objects.filter(image=img).delete()

        # Create new points and annotations.
        new_points = []
        new_annotations = []

        for num, point_dict in enumerate(csv_annotations_for_image, 1):
            # Create a Point.
            point = Point(
                row=point_dict['row'], column=point_dict['column'],
                point_number=num, image=img)
            new_points.append(point)
        # Save to DB with an efficient bulk operation.
        Point.objects.bulk_create(new_points)

        for num, point_dict in enumerate(csv_annotations_for_image, 1):
            # Create an Annotation if a label is specified.
            if 'label' in point_dict:
                label_obj = source.labelset.get_global_by_code(
                    point_dict['label'])
                new_annotations.append(Annotation(
                    point=Point.objects.get(point_number=num, image=img),
                    image=img, source=source,
                    label=label_obj, user=get_imported_user()))
        # Save to DB with an efficient bulk operation.
        # TODO: It may be possible to merge the Point and Annotation
        # creation code more cleanly in Django 1.10:
        # https://github.com/django/django/pull/5936
        Annotation.objects.bulk_create(new_annotations)

        # Update relevant image/metadata fields.
        img.point_generation_method = PointGen.args_to_db_format(
            point_generation_type=PointGen.Types.IMPORTED,
            imported_number_of_points=len(new_points)
        )
        img.save()

        img.metadata.annotation_area = AnnotationAreaUtils.IMPORTED_STR
        img.metadata.save()

        # Update relevant image status fields.
        img.confirmed = (len(new_points) == len(new_annotations))
        img.save()
        img.after_annotation_area_change()

    return JsonResponse(dict(
        success=True,
    ))
