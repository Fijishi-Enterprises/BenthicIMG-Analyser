import json
from django.contrib import messages
from django.core.urlresolvers import reverse
from django.db import transaction
from django.http import HttpResponseRedirect, JsonResponse
from django.shortcuts import render, get_object_or_404
from easy_thumbnails.files import get_thumbnailer
from reversion.models import Version, Revision

from .forms import AnnotationForm, AnnotationAreaPixelsForm, AnnotationToolSettingsForm, AnnotationImageOptionsForm
from .model_utils import AnnotationAreaUtils
from .models import Annotation, AnnotationToolAccess, AnnotationToolSettings
from .utils import get_annotation_version_user_display, image_annotation_all_done, apply_alleviate
from accounts.utils import is_robot_user
from images.models import Source, Image, Point
from images.utils import generate_points, get_next_image, \
    get_date_and_aux_metadata_table, get_prev_image, get_image_order_placement
from lib.decorators import image_permission_required, image_annotation_area_must_be_editable, image_labelset_required, login_required_ajax
from visualization.forms import HiddenForm, post_to_image_filter_form
import vision_backend.tasks as backend_tasks

@image_permission_required('image_id', perm=Source.PermTypes.EDIT.code)
@image_annotation_area_must_be_editable('image_id')
def annotation_area_edit(request, image_id):
    """
    Edit an image's annotation area.
    """

    image = get_object_or_404(Image, id=image_id)
    source = image.source
    metadata = image.metadata

    old_annotation_area = metadata.annotation_area

    if request.method == 'POST':

        # Cancel
        cancel = request.POST.get('cancel', None)
        if cancel:
            messages.success(request, 'Edit cancelled.')
            return HttpResponseRedirect(reverse('image_detail', args=[image.id]))

        # Submit
        annotationAreaForm = AnnotationAreaPixelsForm(request.POST, image=image)

        if annotationAreaForm.is_valid():
            metadata.annotation_area = AnnotationAreaUtils.pixels_to_db_format(**annotationAreaForm.cleaned_data)
            metadata.save()

            if metadata.annotation_area != old_annotation_area:
                generate_points(image, usesourcemethod=False)
                backend_tasks.reset_features(image_id)

            messages.success(request, 'Annotation area successfully edited.')
            return HttpResponseRedirect(reverse('image_detail', args=[image.id]))
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        # Just reached this form page
        annotationAreaForm = AnnotationAreaPixelsForm(image=image)

    # Scale down the image to have a max width of 800 pixels.
    MAX_DISPLAY_WIDTH = 800

    # jQuery UI resizing with containment isn't subpixel-precise, so
    # the display height is rounded to an int.  Thus, need to track
    # width/height scaling factors separately for accurate calculations.
    display_width = min(MAX_DISPLAY_WIDTH, image.original_width)
    width_scale_factor = float(display_width) / image.original_width
    display_height = int(round(image.original_height * width_scale_factor))
    height_scale_factor = float(display_height) / image.original_height

    dimensions = dict(
        displayWidth = display_width,
        displayHeight = display_height,
        fullWidth = image.original_width,
        fullHeight = image.original_height,
        widthScaleFactor = width_scale_factor,
        heightScaleFactor = height_scale_factor,
    )
    thumbnail_dimensions = (display_width, display_height)

    return render(request, 'annotations/annotation_area_edit.html', {
        'source': source,
        'image': image,
        'dimensions': json.dumps(dimensions),
        'thumbnail_dimensions': thumbnail_dimensions,
        'annotationAreaForm': annotationAreaForm,
    })


@image_permission_required('image_id', perm=Source.PermTypes.EDIT.code)
@image_labelset_required('image_id', message=(
    "You need to create a labelset for your source"
    " before you can annotate images."))
def annotation_tool(request, image_id):
    """
    View for the annotation tool.
    """
    image = get_object_or_404(Image, id=image_id)
    source = image.source
    metadata = image.metadata

    # The set of images we're annotating.
    image_set = Image.objects.filter(source=source)
    hidden_image_set_form = None
    filters_used_display = None

    image_form = \
        post_to_image_filter_form(request.POST, source, has_annotation_status=True)
    if image_form:
        if image_form.is_valid():
            image_set = image_form.get_images()
            hidden_image_set_form = HiddenForm(forms=[image_form])
            filters_used_display = image_form.get_filters_used_display()

    # Get the next and previous images in the image set.
    # TODO: Natural-sort by name.
    prev_image = get_prev_image(
        image, image_set,
        ('metadata__name', image.metadata.name, False), wrap=True)
    next_image = get_next_image(
        image, image_set,
        ('metadata__name', image.metadata.name, False), wrap=True)
    # Get the image's ordered placement in the image set, e.g. 5th.
    image_set_order_placement = get_image_order_placement(
        image_set, ('metadata__name', image.metadata.name, False))

    # Get the settings object for this user.
    # If there is no such settings object, then create it.
    settings_obj, created = AnnotationToolSettings.objects.get_or_create(user=request.user)
    settings_form = AnnotationToolSettingsForm(instance=settings_obj)

    # Get labels in the form
    # {'code': <short code>, 'group': <functional group>, 'name': <full name>}.
    labels = source.labelset.get_locals_ordered_by_group_and_code()
    labels = [
        dict(code=label.code, group=label.group.name, name=label.name)
        for label in labels
    ]

    error_message = []
    # Get the machine's label probabilities, if applicable.
    if not settings_obj.show_machine_annotations:
        label_probabilities = None
    elif not image.features.classified:
        label_probabilities = None
    else:
        label_probabilities = None #task_utils.get_label_probabilities_for_image(image_id)
        # label_probabilities can still be None here if something goes wrong.
        # But if not None, apply Alleviate.
        if label_probabilities:
            apply_alleviate(image_id, label_probabilities)
        else:
            error_message.append('Woops! Could not read the label probabilities. Manual annotation still works.')

    # Form where you enter annotations' label codes
    form = AnnotationForm(
        image=image,
        show_machine_annotations=settings_obj.show_machine_annotations
    )

    # List of dicts containing point info
    points = Point.objects.filter(image=image) \
        .order_by('point_number') \
        .values('point_number', 'row', 'column')
    points = list(points)

    # Image tools form (brightness, contrast, etc.)
    image_options_form = AnnotationImageOptionsForm()

    # Image dimensions.
    IMAGE_AREA_WIDTH = 850
    IMAGE_AREA_HEIGHT = 650

    source_images = dict(full=dict(
        url=image.original_file.url,
        width=image.original_file.width,
        height=image.original_file.height,
    ))
    if image.original_width > IMAGE_AREA_WIDTH:
        # Set scaled image's dimensions (Specific width, height that keeps the aspect ratio)
        thumbnail_dimensions = (IMAGE_AREA_WIDTH, 0)

        # Generate the thumbnail if it doesn't exist, and get the thumbnail's URL and dimensions.
        thumbnailer = get_thumbnailer(image.original_file)
        thumb = thumbnailer.get_thumbnail(dict(size=thumbnail_dimensions))
        source_images.update(dict(scaled=dict(
            url=thumb.url,
            width=thumb.width,
            height=thumb.height,
        )))


    # Record this access of the annotation tool page.
    access = AnnotationToolAccess(image=image, source=source, user=request.user)
    access.save()

    return render(request, 'annotations/annotation_tool.html', {
        'source': source,
        'image': image,
        'hidden_image_set_form': hidden_image_set_form,
        'next_image': next_image,
        'prev_image': prev_image,
        'image_set_size': image_set.count(),
        'image_set_order_placement': image_set_order_placement,
        'filters_used_display': filters_used_display,
        'metadata': metadata,
        'image_meta_table': get_date_and_aux_metadata_table(image),
        'labels': labels,
        'form': form,
        'settings_form': settings_form,
        'image_options_form': image_options_form,
        'points': points,
        'label_probabilities': label_probabilities,
        'IMAGE_AREA_WIDTH': IMAGE_AREA_WIDTH,
        'IMAGE_AREA_HEIGHT': IMAGE_AREA_HEIGHT,
        'source_images': source_images,
        'messages': error_message,
    })


@image_permission_required(
    'image_id', perm=Source.PermTypes.EDIT.code, ajax=True)
def save_annotations_ajax(request, image_id):
    """
    Called via Ajax from the annotation tool, if the user clicked
    the Save button.

    Takes the annotation form contents, in request.POST.
    Saves annotation changes to the database.
    JSON response consists of:
      all_done: boolean, True if the image has all points confirmed
      error: error message if there was an error, otherwise not present
    """
    if request.method != 'POST':
        return JsonResponse(dict(
            error="Not a POST request"))

    image = get_object_or_404(Image, id=image_id)
    source = image.source

    # Get stuff from the DB in advance, should save DB querying time
    points_list = list(Point.objects.filter(image=image))
    points = dict([(p.point_number, p) for p in points_list])

    annotations_list = list(
        Annotation.objects.filter(image=image, source=source))
    annotations = dict([(a.point_id, a) for a in annotations_list])

    for point_num, point in points.items():

        label_code = request.POST.get('label_'+str(point_num), None)
        if label_code is None:
            return JsonResponse(
                dict(error="Missing label field for point %s." % point_num))

        # Does the form field have a non-human-confirmed robot annotation?
        is_unconfirmed_in_form_raw = request.POST.get('robot_'+str(point_num))
        if is_unconfirmed_in_form_raw is None:
            return JsonResponse(
                dict(error="Missing robot field for point %s." % point_num))
        is_unconfirmed_in_form = json.loads(is_unconfirmed_in_form_raw)

        # Get the label that the form field value refers to.
        # Anticipate errors, even if we plan to check input with JS.
        if label_code == '':
            label = None
        else:
            label = source.labelset.get_global_by_code(label_code)
            if not label:
                return JsonResponse(dict(error=(
                    "The labelset has no label with code %s." % label_code)))

        # An annotation of this point number exists in the database
        if point.pk in annotations:
            anno = annotations[point.pk]
            # Label field is now blank.
            # We're not allowing label deletions,
            # so don't do anything in this case.
            if label is None:
                pass
            # Label was robot annotated, and then the human user
            # confirmed or changed it
            elif is_robot_user(anno.user) and not is_unconfirmed_in_form:
                anno.label = label
                anno.user = request.user
                anno.save()
            # Label was otherwise changed
            elif label != anno.label:
                anno.label = label
                anno.user = request.user
                anno.save()
            # Else, there's nothing to save, so don't do anything.

        # No annotation of this point number in the database yet
        else:
            if label is not None:
                new_anno = Annotation(
                    point=point, user=request.user,
                    image=image, source=source, label=label)
                new_anno.save()

    # Are all points human annotated?
    all_done = image_annotation_all_done(image)

    # Update image status, if needed
    if image.confirmed != all_done:
        image.confirmed = all_done
        image.save()

    # Finally, with a new image confirmed, let's try to train a new robot.
    # It will simply exit if there is not enough new images or if one is 
    # already being trained.
    backend_tasks.submit_classifier()

    return JsonResponse(dict(all_done=all_done))


@image_permission_required(
    'image_id', perm=Source.PermTypes.VIEW.code, ajax=True)
def is_annotation_all_done_ajax(request, image_id):
    """
    :returns dict of:
      all_done: True if the image has all points confirmed, False otherwise
      error: Error message if there was an error
    """
    image = get_object_or_404(Image, id=image_id)
    return JsonResponse(dict(all_done=image_annotation_all_done(image)))


@login_required_ajax
def annotation_tool_settings_save(request):
    """
    Annotation tool Ajax: user clicks the settings Save button.
    Saves annotation tool settings changes to the database.

    :param the settings form contents, in request.POST
    :returns dict of:
      error: Error message if there was an error
    """

    if request.method != 'POST':
        return JsonResponse(dict(error="Not a POST request"))

    settings_obj = AnnotationToolSettings.objects.get(user=request.user)
    settings_form = AnnotationToolSettingsForm(request.POST, instance=settings_obj)

    if settings_form.is_valid():
        settings_form.save()
        return JsonResponse(dict())
    else:
        # Some form values weren't correct.
        # This can happen if the form's JavaScript input checking isn't
        # foolproof, or if the user messed with form values using FireBug.
        return JsonResponse(dict(error="Part of the form wasn't valid"))


@image_permission_required('image_id', perm=Source.PermTypes.EDIT.code)
# This is a potentially slow view that doesn't modify the database,
# so don't open a transaction for the view.
@transaction.non_atomic_requests
def annotation_history(request, image_id):
    """
    View for an image's annotation history.
    """
    image = get_object_or_404(Image, id=image_id)
    source = image.source

    # Use values_list() and list() to avoid nested queries.
    # https://docs.djangoproject.com/en/1.3/ref/models/querysets/#in
    annotation_values = Annotation.objects.filter(
        image=image, source=source).values('pk', 'point__point_number')
    annotation_ids = [v['pk'] for v in annotation_values]

    # Prefetch versions from the DB using list().
    versions_queryset = Version.objects.filter(
        object_id__in=list(annotation_ids))
    list(versions_queryset)

    revision_pks = \
        versions_queryset.values_list('revision', flat=True).distinct()
    revisions = list(Revision.objects.filter(pk__in=list(revision_pks)))

    # anno_pks_to_pointnums maps each Annotation's pk to the corresponding
    # Point's point number.
    point_number_tuples = [
        (v['pk'], v['point__point_number']) for v in annotation_values]
    anno_pks_to_pointnums = dict()
    for tup in point_number_tuples:
        anno_pks_to_pointnums[tup[0]] = tup[1]

    event_log = []

    for rev in revisions:
        # Get Versions under this Revision
        rev_versions = list(versions_queryset.filter(revision=rev))
        # Sort by the point number of the annotation
        rev_versions.sort(
            key=lambda x: anno_pks_to_pointnums[int(x.object_id)])

        # Create a log entry for this Revision
        events = []
        for v in rev_versions:
            point_number = anno_pks_to_pointnums[int(v.object_id)]
            global_label_pk = v.field_dict['label']
            label_code = source.labelset.global_pk_to_code(global_label_pk)

            events.append("Point {num}: {code}".format(
                num=point_number, code=label_code or "(Deleted label)"))

        if rev.comment:
            events.append(rev.comment)
        event_log.append(
            dict(
                date=rev.date_created,
                # Any Version will do
                user=get_annotation_version_user_display(rev_versions[0]),
                events=events,
            )
        )

    for access in AnnotationToolAccess.objects.filter(image=image):
        # Create a log entry for each annotation tool access
        event_str = "Accessed annotation tool"
        event_log.append(
            dict(
                date=access.access_date,
                user=access.user.username,
                events=[event_str],
            )
        )

    event_log.sort(key=lambda x: x['date'], reverse=True)

    return render(request, 'annotations/annotation_history.html', {
        'source': source,
        'image': image,
        'metadata': image.metadata,
        'image_meta_table': get_date_and_aux_metadata_table(image),
        'event_log': event_log,
    })
