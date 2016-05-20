import json
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.urlresolvers import reverse
from django.db import transaction
from django.http import HttpResponseRedirect, JsonResponse
from django.shortcuts import render, get_object_or_404
from easy_thumbnails.files import get_thumbnailer
from reversion.models import Version, Revision
from accounts.utils import get_robot_user, is_robot_user
import annotations.forms as annotations_forms
import annotations.utils as annotations_utils
from annotations.forms import NewLabelForm, NewLabelSetForm, AnnotationForm, AnnotationAreaPixelsForm, AnnotationToolSettingsForm, AnnotationImageOptionsForm
from annotations.model_utils import AnnotationAreaUtils
from annotations.models import Label, LabelSet, Annotation, AnnotationToolAccess, AnnotationToolSettings
from annotations.utils import get_annotation_version_user_display, image_annotation_all_done
from lib.decorators import source_permission_required, source_visibility_required, image_permission_required, image_annotation_area_must_be_editable, image_labelset_required, login_required_ajax
from images import task_utils
from images.models import Source, Image, Point
from images.utils import generate_points, get_first_image, get_next_image
from visualization.utils import generate_patch_if_doesnt_exist

@login_required
def label_new(request):
    """
    Page to create a new label for CoralNet.
    NOTE: This view might be obsolete, deferring in favor of
    having the new-label form only be in the create-labelset page.
    """
    if request.method == 'POST':
        form = NewLabelForm(request.POST)

        if form.is_valid():
            label = form.save()
            messages.success(request, 'Label successfully created.')
            return HttpResponseRedirect(reverse('label_main', args=[label.id]))
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = NewLabelForm()

    return render(request, 'annotations/label_new.html', {
        'form': form,
    })

@source_permission_required('source_id', perm=Source.PermTypes.ADMIN.code)
def labelset_new(request, source_id):
    """
    Page to create a labelset for a source.
    """

    source = get_object_or_404(Source, id=source_id)
    showLabelForm = False
    initiallyCheckedLabels = []

    if request.method == 'POST':

        initiallyCheckedLabels = [int(labelId) for labelId in request.POST.getlist('labels')]

        if 'create_label' in request.POST:
            labelForm = NewLabelForm(request.POST, request.FILES)
            newLabel = None

            # is_valid() checks for label conflicts in the database (same-name label found, etc.).
            if labelForm.is_valid():
                newLabel = labelForm.instance
                newLabel.created_by = request.user
                newLabel.save()
                messages.success(request, 'Label successfully created.')
            else:
                messages.error(request, 'Please correct the errors below.')
                showLabelForm = True

            # The labelset form should now have the new label.
            labelSetForm = NewLabelSetForm()

            # If a label was added, the user probably wanted to add it to their
            # labelset, so pre-check that label.
            if newLabel:
                initiallyCheckedLabels.append(newLabel.id)

        else:  # 'create_labelset' in request.POST
            labelSetForm = NewLabelSetForm(request.POST)
            labelForm = NewLabelForm()

            if labelSetForm.is_valid():
                labelset = labelSetForm.save()
                source.labelset = labelset
                source.save()

                messages.success(request, 'LabelSet successfully created.')
                return HttpResponseRedirect(reverse('labelset_main', args=[source.id]))
            else:
                messages.error(request, 'Please correct the errors below.')
    
    else:
        labelForm = NewLabelForm()
        labelSetForm = NewLabelSetForm()

    allLabels = [dict(labelId=str(id), name=label.name,
                      code=label.code, group=label.group.name)
                 for id, label in labelSetForm['labels'].field.choices]

    # Dict that tells whether a label should be initially checked: {85: True, 86: True, ...}.
    isInitiallyChecked = dict()
    for labelId, label in labelSetForm['labels'].field.choices:
        isInitiallyChecked[labelId] = labelId in initiallyCheckedLabels
        
    return render(request, 'annotations/labelset_new.html', {
        'showLabelFormInitially': json.dumps(showLabelForm),    # Convert Python bool to JSON bool
        'labelSetForm': labelSetForm,
        'labelForm': labelForm,
        'source': source,
        'isEditLabelsetForm': False,

        'allLabels': allLabels,    # label dictionary, for accessing as a template variable
        'allLabelsJSON': json.dumps(allLabels),    # label dictionary, for JS
        'isInitiallyChecked': json.dumps(isInitiallyChecked),
    })

@source_permission_required('source_id', perm=Source.PermTypes.ADMIN.code)
def labelset_edit(request, source_id):
    """
    Page to edit a source's labelset.
    """

    source = get_object_or_404(Source, id=source_id)

    if source.labelset is None:
        return HttpResponseRedirect(reverse('labelset_new', args=[source.id]))

    labelset = source.labelset
    showLabelForm = False
    labelsInLabelset = [label.id for label in labelset.labels.all()]
    initiallyCheckedLabels = labelsInLabelset

    if request.method == 'POST':

        initiallyCheckedLabels = [int(labelId) for labelId in request.POST.getlist('labels')]

        if 'create_label' in request.POST:
            labelForm = NewLabelForm(request.POST, request.FILES)
            newLabel = None

            # is_valid() checks for label conflicts in the database (same-name label found, etc.).
            if labelForm.is_valid():
                newLabel = labelForm.instance
                newLabel.created_by = request.user
                newLabel.save()
                messages.success(request, 'Label successfully created.')
            else:
                messages.error(request, 'Please correct the errors below.')
                showLabelForm = True

            # The labelset form should now have the new label.
            labelSetForm = NewLabelSetForm()

            # If a label was added, the user probably wanted to add it to their
            # labelset, so pre-check that label.
            if newLabel:
                initiallyCheckedLabels.append(newLabel.id)

        elif 'edit_labelset' in request.POST:
            labelSetForm = NewLabelSetForm(request.POST, instance=labelset)
            labelForm = NewLabelForm()

            if labelSetForm.is_valid():
                labelSetForm.save()

                messages.success(request, 'LabelSet successfully edited.')
                return HttpResponseRedirect(reverse('labelset_main', args=[source.id]))
            else:
                messages.error(request, 'Please correct the errors below.')

        else: # Cancel
            messages.success(request, 'Edit cancelled.')
            return HttpResponseRedirect(reverse('labelset_main', args=[source_id]))

    else:
        labelForm = NewLabelForm()
        labelSetForm = NewLabelSetForm(instance=labelset)

    # Dictionary of info for each label in the labelset form.
    allLabels = [dict(labelId=str(id), name=label.name,
                      code=label.code, group=label.group.name)
                 for id, label in labelSetForm['labels'].field.choices]

    # Dict that tells whether a label is already in the labelset: {85: True, 86: True, ...}.
    # This is basically a workaround around JavaScript's lack of a widely supported "is element in list" function.
    isInLabelset = dict()
    for labelId, label in labelSetForm['labels'].field.choices:
        isInLabelset[labelId] = labelId in labelsInLabelset

    # Dict that tells whether a label should be initially checked: {85: True, 86: True, ...}.
    isInitiallyChecked = dict()
    for labelId, label in labelSetForm['labels'].field.choices:
        isInitiallyChecked[labelId] = labelId in initiallyCheckedLabels

    # Dict that tells whether an initially-checked label's status is changeable: {85: True, 86: False, ...}.
    # A label is unchangeable if it's being used by any annotations in this source.
    isLabelUnchangeable = dict()
    for labelId, label in labelSetForm['labels'].field.choices:
        if labelId in initiallyCheckedLabels:
            annotationsForLabel = Annotation.objects.filter(image__source=source, label__id=labelId)
            isLabelUnchangeable[labelId] = len(annotationsForLabel) > 0
        else:
            isLabelUnchangeable[labelId] = False


    return render(request, 'annotations/labelset_edit.html', {
        'showLabelFormInitially': json.dumps(showLabelForm),    # Python bool to JSON bool
        'labelSetForm': labelSetForm,
        'labelForm': labelForm,
        'source': source,
        'isEditLabelsetForm': True,

        'allLabels': allLabels,    # label dictionary, for accessing as a template variable
        'allLabelsJSON': json.dumps(allLabels),    # label dictionary, for JS
        'isInLabelset': json.dumps(isInLabelset),
        'isInitiallyChecked': json.dumps(isInitiallyChecked),
        'isLabelUnchangeable': json.dumps(isLabelUnchangeable),
    })

def label_main(request, label_id):
    """
    Main page for a particular label
    """

    label = get_object_or_404(Label, id=label_id)

    sources_with_label = Source.objects.filter(labelset__labels=label).order_by('name')
    visible_sources_with_label = [s for s in sources_with_label if s.visible_to_user(request.user)]

    # Differentiate between the sources that the user is part of
    # and the other public sources.  Sort the source list accordingly, too.
    sources_of_user = Source.get_sources_of_user(request.user)

    source_types = []
    for s in visible_sources_with_label:
        if s in sources_of_user:
            source_types.append('mine')
        else:
            source_types.append('public')

    visible_sources_with_label = zip(source_types, visible_sources_with_label)
    visible_sources_with_label.sort(key=lambda x: x[0])  # Mine first, then public

    # Example patches.
    # TODO: don't hardcode the patch path
    example_annotations = Annotation.objects.filter(label=label, image__source__visibility=Source.VisibilityTypes.PUBLIC).exclude(user=get_robot_user()).order_by('?')[:5]
    patches = [dict(
                  annotation=a,
                  fullImage=a.image,
                  source=a.image.source,
                  patchPath="data/annotations/" + str(a.id) + ".jpg",
                  row=a.point.row,
                  col=a.point.column,
                  pointNum=a.point.point_number,
              )
              for a in example_annotations]

    for p in patches:
        generate_patch_if_doesnt_exist(p['patchPath'], p['annotation'])


    return render(request, 'annotations/label_main.html', {
        'label': label,
        'visible_sources_with_label': visible_sources_with_label,
        'patches': patches,
    })


@source_visibility_required('source_id')
def labelset_main(request, source_id):
    """
    Main page for a particular source's labelset
    """

    source = get_object_or_404(Source, id=source_id)

    if source.labelset is None:
        return HttpResponseRedirect(reverse('labelset_new', args=[source.id]))

    labelset = source.labelset
    labels = labelset.labels.all().order_by('group__id', 'name')


    return render(request, 'annotations/labelset_main.html', {
        'source': source,
        'labelset': labelset,
        'labels': labels,
    })

def labelset_list(request):
    """
    Page with a list of all the labelsets

    Not sure where to put a link to this page. It's a little less
    useful when each source has its own labelset, but this view still
    might be useful if someone wants to browse through labelsets that
    they could base their labelset off of.
    """

    publicSources = Source.objects.filter(visibility=Source.VisibilityTypes.PUBLIC)
    publicSourcesWithLabelsets = publicSources.exclude(labelset=None)

    return render(request, 'annotations/labelset_list.html', {
        'publicSourcesWithLabelsets': publicSourcesWithLabelsets,
    })

def label_list(request):
    """
    Page with a list of all the labels
    """

    labels = Label.objects.all().order_by('group__id', 'name')

    return render(request, 'annotations/label_list.html', {
        'labels': labels,
    })



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
                image.after_annotation_area_change()

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
@image_labelset_required('image_id', message='You need to create a labelset for your source before you can annotate images.')
def annotation_tool(request, image_id):
    """
    View for the annotation tool.
    """

    image = get_object_or_404(Image, id=image_id)
    source = image.source
    metadata = image.metadata


    # Image navigation history.
    # Establish default values for the history, first.
    nav_history_form =\
        annotations_forms.AnnotationToolNavHistoryForm(
            initial=dict(back="[]", forward="[]", from_image_id=image_id)
        )
    nav_history = dict(
        form=nav_history_form,
        back=None,
        forward=None,
    )
    # We made a POST request if the user is going to another image,
    # going back, or going forward.
    # (It's non-POST if they came from a non annotation tool page, or
    # came via URL typing.)
    if request.method == 'POST':
        nav_history_form_submitted =\
            annotations_forms.AnnotationToolNavHistoryForm(request.POST)

        if nav_history_form_submitted.is_valid():
            # Nav history is a serialized list of image ids.
            # For example: "[258,259,268,109]"
            form_data = nav_history_form_submitted.cleaned_data
            back_submitted_list = json.loads(form_data['back'])
            forward_submitted_list = json.loads(form_data['forward'])
            from_image_id = form_data['from_image_id']

            # Construct new back and forward lists based on
            # where we're navigating.
            if request.POST.get('nav_next', None):
                back_list = back_submitted_list + [from_image_id]
                forward_list = []
            elif request.POST.get('nav_back', None):
                back_list = back_submitted_list[:-1]
                forward_list = [from_image_id] + forward_submitted_list
            else:  # 'nav_forward'
                back_list = back_submitted_list + [from_image_id]
                forward_list = forward_submitted_list[1:]

            limit = 10
            nav_history_form = \
                annotations_forms.AnnotationToolNavHistoryForm(
                    initial=dict(
                        back=json.dumps(back_list[-limit:]),
                        forward=json.dumps(forward_list[:limit]),
                        from_image_id=image_id,
                    )
                )

            if len(back_list) > 0:
                back = Image.objects.get(pk=back_list[-1])
            else:
                back = None
            if len(forward_list) > 0:
                forward = Image.objects.get(pk=forward_list[0])
            else:
                forward = None
            nav_history = dict(
                form=nav_history_form,
                back=back,
                forward=forward,
            )
        else:
            # Invalid form for some reason.
            # Fail silently, I guess? That is, use an empty history.
            pass


    # Get the settings object for this user.
    # If there is no such settings object, then create it.
    settings_obj, created = AnnotationToolSettings.objects.get_or_create(user=request.user)
    settings_form = AnnotationToolSettingsForm(instance=settings_obj)


    # Get all labels, ordered first by functional group, then by short code.
    labels = source.labelset.labels.all().order_by('group', 'code')
    # Get labels in the form
    # {'code': <short code>, 'group': <functional group>, 'name': <full name>}.
    # Convert from a QuerySet to a list to ensure it's JSON-serializable.
    labelValues = list(labels.values('code', 'group', 'name'))

    error_message = []
    # Get the machine's label probabilities, if applicable.
    if not settings_obj.show_machine_annotations:
        label_probabilities = None
    elif not image.status.annotatedByRobot:
        label_probabilities = None
    else:
        label_probabilities = task_utils.get_label_probabilities_for_image(image_id)
        # label_probabilities can still be None here if something goes wrong.
        # But if not None, apply Alleviate.
        if label_probabilities:
            annotations_utils.apply_alleviate(image_id, label_probabilities)
        else:
            error_message.append('Woops! Could not read the label probabilities. Manual annotation still works.')


    # Get points and annotations.
    form = AnnotationForm(
        image=image,
        show_machine_annotations=settings_obj.show_machine_annotations
    )

    pointValues = Point.objects.filter(image=image).values(
        'point_number', 'row', 'column')
    annotationValues = Annotation.objects.filter(image=image).values(
        'point__point_number', 'label__name', 'label__code')

    # annotationsDict
    # keys: point numbers
    # values: dicts containing the values in pointValues and
    #         annotationValues (if the point has an annotation) above
    annotationsDict = dict()
    for p in pointValues:
        annotationsDict[p['point_number']] = p
    for a in annotationValues:
        annotationsDict[a['point__point_number']].update(a)

    # Get a list of the annotationsDict values (the keys are discarded)
    # Sort by point_number
    annotations = list(annotationsDict.values())
    annotations.sort(key=lambda x:x['point_number'])

    # Now we've gotten all the relevant points and annotations
    # from the database, in a list of dicts:
    # [{'point_number':1, 'row':294, 'column':749, 'label__name':'Porites', 'label__code':'Porit', 'user_is_robot':False},
    #  {'point_number':2, ...},
    #  ...]
    # TODO: Are we even using anything besides row, column, and point_number?  If not, discard the annotation fields to avoid confusion.


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


    # Get the next image to annotate.
    # This'll be the next image that needs annotation;
    # or if we're at the last image, wrap around to the first image.
    next_image_to_annotate = get_next_image(image, dict(status__annotatedByHuman=False))

    if next_image_to_annotate is None:
        next_image_to_annotate = get_first_image(
            image.source, dict(status__annotatedByHuman=False)
        )
        # Don't allow getting the current image as the next image to annotate.
        if next_image_to_annotate is not None and next_image_to_annotate.id == image.id:
            next_image_to_annotate = None


    # Record this access of the annotation tool page.
    access = AnnotationToolAccess(image=image, source=source, user=request.user)
    access.save()

    return render(request, 'annotations/annotation_tool.html', {
        'source': source,
        'image': image,
        'next_image_to_annotate': next_image_to_annotate,
        'nav_history': nav_history,
        'metadata': metadata,
        'labels': labelValues,
        'form': form,
        'settings_form': settings_form,
        'image_options_form': image_options_form,
        'annotations': annotations,
        'annotationsJSON': json.dumps(annotations),
        'label_probabilities': label_probabilities,
        'IMAGE_AREA_WIDTH': IMAGE_AREA_WIDTH,
        'IMAGE_AREA_HEIGHT': IMAGE_AREA_HEIGHT,
        'source_images': source_images,
        'num_of_points': len(annotations),
        'num_of_annotations': len(annotationValues),
        'messages': error_message,
    })


@image_permission_required(
    'image_id', perm=Source.PermTypes.EDIT.code, ajax=True)
def save_annotations_ajax(request, image_id):
    """
    Called via Ajax from the annotation tool, if the user clicked
    the Save button.
    Saves annotation changes to the database.

    :param the annotation form contents, in request.POST
    :returns dict of:
      all_done (optional): True if the image has all points confirmed
      error: Error message if there was an error
    """

    if request.method != 'POST':
        return JsonResponse(dict(
            error="Not a POST request",
        ))

    image = get_object_or_404(Image, id=image_id)
    source = image.source
    sourceLabels = source.labelset.labels.all()

    # Get stuff from the DB in advance, should save DB querying time
    pointsList = list(Point.objects.filter(image=image))
    points = dict([ (p.point_number, p) for p in pointsList ])

    annotationsList = list(Annotation.objects.filter(image=image, source=source))
    annotations = dict([ (a.point_id, a) for a in annotationsList ])

    for pointNum in points.keys():

        labelCode = request.POST['label_'+str(pointNum)]

        # Does the form field have a non-human-confirmed robot annotation?
        isFormRobotAnnotation = json.loads(
            request.POST['robot_'+str(pointNum)])

        point = points[pointNum]

        # Get the label that the form field value refers to.
        # Anticipate errors, even if we plan to check input with JS.
        if labelCode == '':
            label = None
        else:
            labels = Label.objects.filter(code=labelCode)
            if len(labels) == 0:
                return JsonResponse(
                    dict(error="No label with code %s." % labelCode))

            label = labels[0]
            if label not in sourceLabels:
                return JsonResponse(
                    dict(error="The labelset has no label with code %s." % labelCode))

        # An annotation of this point number exists in the database
        if annotations.has_key(point.id):
            anno = annotations[point.id]
            # Label field is now blank.
            # We're not allowing label deletions,
            # so don't do anything in this case.
            if label is None:
                pass
            # Label was robot annotated, and then the human user
            # confirmed or changed it
            elif is_robot_user(anno.user) and not isFormRobotAnnotation:
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
                newAnno = Annotation(point=point, user=request.user, image=image, source=source, label=label)
                newAnno.save()

    # Are all points human annotated?
    all_done = image_annotation_all_done(image)

    # Update image status, if needed
    if image.status.annotatedByHuman:
        image.after_completed_annotations_change()
    if image.status.annotatedByHuman != all_done:
        image.status.annotatedByHuman = all_done
        image.status.save()

    if all_done:
        return JsonResponse(dict(all_done=True))
    else:
        return JsonResponse(dict())


@image_permission_required(
    'image_id', perm=Source.PermTypes.EDIT.code, ajax=True)
def is_annotation_all_done_ajax(request, image_id):
    """
    :returns dict of:
      all_done: True if the image has all points confirmed, False otherwise
      error: Error message if there was an error
    """

    if request.method != 'POST':
        return JsonResponse(dict(error="Not a POST request"))

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
    annotation_values = Annotation.objects.filter(image=image, source=source).values('pk', 'point__point_number')
    annotation_ids = [v['pk'] for v in annotation_values]

    # Prefetch versions from the DB.
    versions_queryset = Version.objects.filter(object_id__in=list(annotation_ids))
    versions = list(versions_queryset)   # list() prefetches.

    # label_pks_to_codes maps Label pks to the corresponding Label's short code.
    label_pks = set([v.field_dict['label'] for v in versions])
    labels = Label.objects.filter(pk__in=label_pks).values_list('pk', 'code')
    label_pks_to_codes = dict(labels)
    for pk in label_pks:
        if pk not in label_pks_to_codes:
            label_pks_to_codes[pk] = "(Deleted label)"

    revision_pks = versions_queryset.values_list('revision', flat=True).distinct()
    revisions = list(Revision.objects.filter(pk__in=list(revision_pks)))

    # anno_pks_to_pointnums maps each Annotation's pk to the corresponding
    # Point's point number.
    point_number_tuples = [(v['pk'], v['point__point_number']) for v in annotation_values]
    anno_pks_to_pointnums = dict()
    for tup in point_number_tuples:
        anno_pks_to_pointnums[tup[0]] = tup[1]

    event_log = []

    for rev in revisions:
        # Get Versions under this Revision
        rev_versions = list(versions_queryset.filter(revision=rev))
        # Sort by the point number of the annotation
        rev_versions.sort( key=lambda x: anno_pks_to_pointnums[int(x.object_id)] )

        # Create a log entry for this Revision
        events = ["Point {num}: {code}".format(
                num=anno_pks_to_pointnums[int(v.object_id)],
                code=label_pks_to_codes[v.field_dict['label']],
            )
            for v in rev_versions
        ]
        if rev.comment:
            events.append(rev.comment)
        event_log.append(
            dict(
                date=rev.date_created,
                user=get_annotation_version_user_display(rev_versions[0]),  # Any Version will do
                events=events,
            )
        )

    for access in AnnotationToolAccess.objects.filter(image=image, source=source):
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
        'event_log': event_log,
    })