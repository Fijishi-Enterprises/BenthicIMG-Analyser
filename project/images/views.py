import datetime
from urllib.parse import urlencode

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.http import HttpResponseRedirect
from django.shortcuts import redirect, render, get_object_or_404
from django.urls import reverse
from django.views.decorators.http import require_POST

from annotations.forms import AnnotationAreaPercentsForm
from annotations.model_utils import (
    AnnotationAreaUtils,
    ImageAnnoStatuses,
    image_annotation_verbose_status_label,
)
from annotations.models import Annotation
from annotations.utils import (
    get_sitewide_annotation_count,
    image_annotation_area_is_editable,
    image_has_any_confirmed_annotations,
)
from jobs.utils import queue_job
from labels.models import LabelGroup
from lib.decorators import (
    image_annotation_area_must_be_editable,
    image_permission_required,
    image_visibility_required,
    source_permission_required,
    source_visibility_required,
)
from map.utils import get_map_sources
from newsfeed.models import NewsItem
from vision_backend.models import Classifier
from vision_backend.utils import reset_features
from . import utils
from .forms import (
    ImageSourceForm,
    MetadataForm,
    PointGenForm,
    SourceChangePermissionForm,
    SourceInviteForm,
    SourceRemoveUserForm,
)
from .model_utils import PointGen
from .models import Source, Image, SourceInvite, Metadata


def source_list(request):
    """
    Page with a list of the user's Sources.
    """
    your_sources = Source.get_sources_of_user(request.user)

    # Redirect to the About page if the user doesn't have any Sources.
    # This includes the not-logged-in case.
    if not your_sources:
        return HttpResponseRedirect(reverse('source_about'))

    your_sources_dicts = [dict(id=s.id,
                               name=s.name,
                               your_role=s.get_member_role(request.user),)
                          for s in your_sources]
    other_public_sources = Source.get_other_public_sources(request.user)

    # Gather some stats
    total_sources = Source.objects.all().count()
    total_images = Image.objects.all().count()
    total_annotations = get_sitewide_annotation_count()

    return render(request, 'images/source_list.html', {
        'your_sources': your_sources_dicts,
        'map_sources': get_map_sources(),
        'other_public_sources': other_public_sources,
        'total_sources': total_sources,
        'total_images': total_images,
        'total_annotations': total_annotations,
    })


def source_about(request):
    """
    Page that explains what Sources are and how to use them.
    """

    if request.user.is_authenticated:
        if Source.get_sources_of_user(request.user):
            user_status = 'has_sources'
        else:
            user_status = 'no_sources'
    else:
        user_status = 'anonymous'

    return render(request, 'images/source_about.html', {
        'user_status': user_status,
        'public_sources': Source.get_public_sources(),
    })


@login_required
def source_new(request):
    """
    Page with the form to create a new Source.
    """

    # We can get here one of two ways: either we just got to the form
    # page, or we just submitted the form.  If POST, we submitted; if
    # GET, we just got here.
    if request.method == 'POST':
        # Bind the forms to the submitted POST data.
        sourceForm = ImageSourceForm(request.POST)
        pointGenForm = PointGenForm(request.POST)
        annotationAreaForm = AnnotationAreaPercentsForm(request.POST)

        # <form>.is_valid() calls <form>.clean() and checks field validity.
        # Make sure is_valid() is called for all forms, so all forms are checked and
        # all relevant error messages appear.
        source_form_is_valid = sourceForm.is_valid()
        point_gen_form_is_valid = pointGenForm.is_valid()
        annotation_area_form_is_valid = annotationAreaForm.is_valid()

        if source_form_is_valid and point_gen_form_is_valid \
         and annotation_area_form_is_valid:

            # Since sourceForm is a ModelForm, after calling sourceForm's
            # is_valid(), a Source instance is created.  We retrieve this
            # instance and add the other values to it before saving to the DB.
            newSource = sourceForm.instance

            newSource.default_point_generation_method = PointGen.args_to_db_format(**pointGenForm.cleaned_data)
            newSource.image_annotation_area = AnnotationAreaUtils.percentages_to_db_format(**annotationAreaForm.cleaned_data)
            newSource.save()

            # Make the current user an admin of the new source
            newSource.assign_role(request.user, Source.PermTypes.ADMIN.code)

            # Add a success message
            messages.success(request, 'Source successfully created.')
            
            # Redirect to the source's main page
            return HttpResponseRedirect(reverse('source_main', args=[newSource.id]))
        else:
            # Show the form again, with error message
            messages.error(request, 'Please correct the errors below.')
    else:
        # Unbound (empty) forms
        sourceForm = ImageSourceForm()
        pointGenForm = PointGenForm()
        annotationAreaForm = AnnotationAreaPercentsForm()

    # RequestContext is needed for CSRF verification of the POST form,
    # and to correctly get the path of the CSS file being used.
    return render(request, 'images/source_new.html', {
        'sourceForm': sourceForm,
        'pointGenForm': pointGenForm,
        'annotationAreaForm': annotationAreaForm,
        'map_minimum_images': settings.MAP_IMAGE_COUNT_TIERS[0],
    })


@source_visibility_required('source_id')
def source_main(request, source_id):
    """
    Main page for a particular source.
    """

    source = get_object_or_404(Source, id=source_id)

    # Users who are members of the source
    members = source.get_members_ordered_by_role()
    memberDicts = [dict(pk=member.pk,
                        username=member.username,
                        role=source.get_member_role(member))
                   for member in members]

    all_images = source.image_set.all()
    latest_images = all_images.order_by('-upload_date')[:3]

    # Images' annotation status
    browse_url_base = reverse('browse_images', args=[source.id])

    def browse_link_filtered_by_status(annotation_status):
        return browse_url_base + '?' + urlencode(dict(
            image_form_type='search', annotation_status=annotation_status,
            sort_direction='asc', sort_method='name'))

    image_stats = dict(
        total = all_images.count(),
        total_link = browse_url_base,
        confirmed = all_images.confirmed().count(),
        confirmed_link = browse_link_filtered_by_status(
            ImageAnnoStatuses.CONFIRMED.value),
        unconfirmed = all_images.unconfirmed().count(),
        unconfirmed_link = browse_link_filtered_by_status(
            ImageAnnoStatuses.UNCONFIRMED.value),
        unclassified = all_images.unclassified().count(),
        unclassified_link = browse_link_filtered_by_status(
            ImageAnnoStatuses.UNCLASSIFIED.value),
    )

    # Setup the classifier overview plot
    clfs = source.get_accepted_robots()
    robot_stats = dict()
    if clfs.count() > 0:
        backend_plot_data = []
        for enu, clf in enumerate(clfs[::-1]):
            backend_plot_data.append({
                'x': enu + 1,
                'y': round(100 * clf.accuracy),
                'nimages': clf.nbr_train_images, 
                'traintime': str(datetime.timedelta(seconds = clf.runtime_train)),
                'date': str(clf.train_completion_date.strftime("%Y-%m-%d")),
                'pk': str(clf.pk),
            })
        robot_stats['backend_plot_data'] = backend_plot_data
        robot_stats['has_robot'] = True

        robot_stats['last_classifier_saved_date'] = \
            source.get_current_classifier().train_completion_date

        trained_classifiers = source.classifier_set.filter(
            status__in=[Classifier.ACCEPTED, Classifier.REJECTED_ACCURACY])
        robot_stats['last_classifier_trained_date'] = \
            trained_classifiers.latest('pk').train_completion_date
    else:
        robot_stats['has_robot'] = False

    source.latitude = source.latitude[:8]
    source.longitude = source.longitude[:8]

    return render(request, 'images/source_main.html', {
        'source': source,
        'members': memberDicts,
        'latest_images': latest_images,
        'image_stats': image_stats,
        'robot_stats': robot_stats,
        'min_nbr_annotated_images': settings.TRAINING_MIN_IMAGES,
        'news_items': [item.render_view() for item in
                       NewsItem.objects.filter(source_id=source.id).order_by('-pk')]
    })


@source_permission_required('source_id', perm=Source.PermTypes.ADMIN.code)
def source_edit(request, source_id):
    """
    Edit a source: name, visibility, aux. metadata, etc.
    """
    source = get_object_or_404(Source, id=source_id)

    if request.method == 'POST':

        sourceForm = ImageSourceForm(request.POST, instance=source)
        pointGenForm = PointGenForm(request.POST)
        annotationAreaForm = AnnotationAreaPercentsForm(request.POST)

        # Make sure is_valid() is called for all forms, so all forms are checked and
        # all relevant error messages appear.
        source_form_is_valid = sourceForm.is_valid()
        point_gen_form_is_valid = pointGenForm.is_valid()
        annotation_area_form_is_valid = annotationAreaForm.is_valid()

        if source_form_is_valid and point_gen_form_is_valid \
         and annotation_area_form_is_valid:

            editedSource = sourceForm.instance

            editedSource.default_point_generation_method = PointGen.args_to_db_format(**pointGenForm.cleaned_data)
            editedSource.image_annotation_area = AnnotationAreaUtils.percentages_to_db_format(**annotationAreaForm.cleaned_data)

            if 'feature_extractor_setting' in sourceForm.changed_data:

                # Feature extractor setting changed. Wipe this source's
                # features and classifiers.
                editedSource.save()
                queue_job(
                    'reset_backend_for_source', source_id,
                    source_id=source_id)
                messages.success(
                    request,
                    "Source successfully edited."
                    " Classifier history will be cleared.")

            else:

                editedSource.save()
                messages.success(request, "Source successfully edited.")

            return HttpResponseRedirect(reverse('source_main', args=[source_id]))

        else:

            messages.error(request, 'Please correct the errors below.')
    else:
        # Just reached this form page
        sourceForm = ImageSourceForm(instance=source)
        pointGenForm = PointGenForm(source=source)
        annotationAreaForm = AnnotationAreaPercentsForm(source=source)

    return render(request, 'images/source_edit.html', {
        'source': source,
        'editSourceForm': sourceForm,
        'pointGenForm': pointGenForm,
        'annotationAreaForm': annotationAreaForm,
        'map_minimum_images': settings.MAP_IMAGE_COUNT_TIERS[0],
    })


@source_permission_required('source_id', perm=Source.PermTypes.ADMIN.code)
def source_edit_cancel(request, source_id):
    messages.success(request, "Edit cancelled.")
    return redirect('source_main', source_id)


def source_detail_box(request, source_id):
    source = get_object_or_404(Source, id=source_id)

    example_images = source.image_set.all().order_by('-upload_date')[:6]

    return render(request, 'images/source_detail_box.html', {
        'source': source,
        'example_images': example_images,
    })


@source_permission_required('source_id', perm=Source.PermTypes.ADMIN.code)
def source_admin(request, source_id):
    """
    Either invites a user to the source or changes their permission in the source.
    """

    source = get_object_or_404(Source, id=source_id)

    if request.method == 'POST':

        inviteForm = SourceInviteForm(request.POST, source_id=source_id)
        changePermissionForm = SourceChangePermissionForm(request.POST, source_id=source_id, user=request.user)
        removeUserForm = SourceRemoveUserForm(request.POST, source_id=source_id, user=request.user)
        sendInvite = request.POST.get('sendInvite', None)
        changePermission = request.POST.get('changePermission', None)
        removeUser = request.POST.get('removeUser', None)
        deleteSource = request.POST.get('Delete', None)

        if inviteForm.is_valid() and sendInvite:

            invite = SourceInvite(
                sender=request.user,
                recipient=User.objects.get(username=inviteForm.cleaned_data['recipient']),
                source=source,
                source_perm=inviteForm.cleaned_data['source_perm'],
            )
            invite.save()

            messages.success(request, 'Your invite has been sent!')
            return HttpResponseRedirect(reverse('source_main', args=[source_id]))
        elif changePermissionForm.is_valid() and changePermission:

            source.reassign_role(
                user=User.objects.get(id=changePermissionForm.cleaned_data['user']),
                role=changePermissionForm.cleaned_data['perm_change']
            )

            messages.success(request, 'Permission for user has changed.')
            return HttpResponseRedirect(reverse('source_main', args=[source_id]))
        elif removeUserForm.is_valid() and removeUser:
            source.remove_role(User.objects.get(id=removeUserForm.cleaned_data['user']))

            messages.success(request, 'User has been removed from the source.')
            return HttpResponseRedirect(reverse('source_main', args=[source_id]))
        elif deleteSource:
            # Delete all images with our utility function to ensure no
            # problems like leftover related objects.
            images = source.get_all_images()
            for img in images:
                utils.delete_image(img)

            # This is a ForeignKey field of the Source, and thus deleting
            # the Source can't trigger a cascade delete on this labelset.
            # So we have to get the labelset and delete it separately.
            # Also, we delete it after deleting the source to not trigger
            # PROTECT-related errors on this ForeignKey.
            labelset = source.labelset

            source.delete()
            if labelset:
                labelset.delete()

            messages.success(request, 'Source has been deleted.')
            
            return HttpResponseRedirect(reverse('index'))
          
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        # Just reached this form page
        inviteForm = SourceInviteForm(source_id=source_id)
        changePermissionForm = SourceChangePermissionForm(source_id=source_id, user=request.user)
        removeUserForm = SourceRemoveUserForm(source_id=source_id, user=request.user)

    return render(request, 'images/source_invite.html', {
        'source': source,
        'inviteForm': inviteForm,
        'changePermissionForm': changePermissionForm,
        'removeUserForm': removeUserForm,
    })


@login_required
def invites_manage(request):
    """
    Manage sent and received invites.
    """

    if request.method == 'POST':

        if ('accept' in request.POST) or ('decline' in request.POST):
            sender_id = request.POST['sender']
            source_id = request.POST['source']

            try:
                invite = SourceInvite.objects.get(sender__id=sender_id, recipient=request.user, source__id=source_id)
            except SourceInvite.DoesNotExist:
                messages.error(request, "Sorry, there was an error with this invite.\n"
                                        "Maybe the user who sent it withdrew the invite, or you already accepted or declined earlier.")
            else:
                if 'accept' in request.POST:
                    source = Source.objects.get(id=source_id)
                    source.assign_role(invite.recipient, invite.source_perm)

                    invite.delete()
                    messages.success(request, 'Invite accepted!')
                    return HttpResponseRedirect(reverse('source_main', args=[source.id]))
                elif 'decline' in request.POST:
                    invite.delete()
                    messages.success(request, 'Invite declined.')

        elif 'delete' in request.POST:
            recipient_id = request.POST['recipient']
            source_id = request.POST['source']

            try:
                invite = SourceInvite.objects.get(recipient__id=recipient_id, sender=request.user, source__id=source_id)
            except SourceInvite.DoesNotExist:
                messages.error(request, "Sorry, there was an error with this invite.\n"
                                        "Maybe you already deleted it earlier, or the user who received it already accepted or declined.")
            else:
                invite.delete()
                messages.success(request, 'Invite deleted.')

    return render(request, 'images/invites_manage.html', {
        'invitesSent': request.user.invites_sent.all(),
        'invitesReceived': request.user.invites_received.all(),
    })


@image_visibility_required('image_id')
def image_detail(request, image_id):
    """
    View for seeing an image's full size and details/metadata.
    """
    image = get_object_or_404(Image, id=image_id)
    source = image.source
    metadata = image.metadata

    other_fields = [
        dict(
            name=field_name,
            # Field's verbose name in title case (name -> Name)
            label=Metadata._meta.get_field(field_name).verbose_name.title(),
            value=getattr(metadata, field_name),
        )
        for field_name in [
            'height_in_cm', 'latitude', 'longitude', 'depth',
            'camera', 'photographer', 'water_quality', 'strobes',
            'framing', 'balance', 'comments',
        ]
    ]

    # Feel free to change this constant according to the page layout.
    MAX_SCALED_WIDTH = 800
    if image.original_width > MAX_SCALED_WIDTH:
        # Parameters into the easy_thumbnails template tag:
        # (specific width, height that keeps the aspect ratio)
        thumbnail_dimensions = (MAX_SCALED_WIDTH, 0)
    else:
        # No thumbnail needed
        thumbnail_dimensions = False

    # Next and previous image links.
    # Ensure the ordering is unambiguous.
    source_images = source.image_set.order_by('metadata__name', 'pk')
    next_image = utils.get_next_image(image, source_images, wrap=False)
    prev_image = utils.get_prev_image(image, source_images, wrap=False)

    return render(request, 'images/image_detail.html', {
        'source': source,
        'image': image,
        'next_image': next_image,
        'prev_image': prev_image,
        'metadata': metadata,
        'image_meta_table': utils.get_date_and_aux_metadata_table(image),
        'other_fields': other_fields,
        'has_thumbnail': bool(thumbnail_dimensions),
        'thumbnail_dimensions': thumbnail_dimensions,
        'annotation_status': image_annotation_verbose_status_label(image),
        # The boolean flags below determine what actions can be performed
        # on the image.
        'annotation_area_editable':
            image_annotation_area_is_editable(image),
        'has_any_confirmed_annotations':
            image_has_any_confirmed_annotations(image),
        'point_gen_method_synced':
            image.point_generation_method
            == source.default_point_generation_method,
        'annotation_area_synced':
            image.metadata.annotation_area == source.image_annotation_area,
    })


@image_permission_required('image_id', perm=Source.PermTypes.EDIT.code)
def image_detail_edit(request, image_id):
    """
    Edit image details.
    """

    image = get_object_or_404(Image, id=image_id)
    source = image.source
    metadata = image.metadata

    old_height_in_cm = metadata.height_in_cm

    if request.method == 'POST':

        # Cancel
        cancel = request.POST.get('cancel', None)
        if cancel:
            messages.success(request, 'Edit cancelled.')
            return HttpResponseRedirect(reverse('image_detail', args=[image.id]))

        # Submit
        metadata_form = MetadataForm(
            request.POST, instance=metadata, source=source)

        if metadata_form.is_valid():
            editedMetadata = metadata_form.instance
            editedMetadata.save()
            messages.success(request, 'Image successfully edited.')
            return HttpResponseRedirect(reverse('image_detail', args=[image.id]))
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        # Just reached this form page
        metadata_form = MetadataForm(instance=metadata, source=source)

    return render(request, 'images/image_detail_edit.html', {
        'source': source,
        'image': image,
        'metadata_form': metadata_form,
    })


@image_permission_required('image_id', perm=Source.PermTypes.EDIT.code)
@require_POST
def image_delete(request, image_id):
    """
    Delete a single image.
    """
    image = get_object_or_404(Image, id=image_id)

    image_name = image.metadata.name
    source_id = image.source_id
    utils.delete_image(image)

    messages.success(request, 'Successfully deleted image ' + image_name + '.')
    return HttpResponseRedirect(reverse('source_main', args=[source_id]))


@image_permission_required('image_id', perm=Source.PermTypes.EDIT.code)
@require_POST
def image_delete_annotations(request, image_id):
    """
    Delete an image's annotations.
    """
    image = get_object_or_404(Image, id=image_id)

    Annotation.objects.filter(image=image).delete()

    messages.success(
        request, 'Successfully removed all annotations from this image.')
    return HttpResponseRedirect(reverse('image_detail', args=[image_id]))


@image_permission_required('image_id', perm=Source.PermTypes.EDIT.code)
@image_annotation_area_must_be_editable('image_id')
@require_POST
def image_regenerate_points(request, image_id):
    """
    Regenerate an image's point locations, using the image's current
    point generation method and annotation area.
    """
    image = get_object_or_404(Image, id=image_id)

    utils.generate_points(image, usesourcemethod=False)

    reset_features(image)

    messages.success(request, 'Successfully regenerated point locations.')
    return HttpResponseRedirect(reverse('image_detail', args=[image_id]))


@image_permission_required('image_id', perm=Source.PermTypes.EDIT.code)
@image_annotation_area_must_be_editable('image_id')
@require_POST
def image_reset_point_generation_method(request, image_id):
    """
    Reset an image's point generation method to the source's default.
    This regenerates the image's points as well.
    """
    image = get_object_or_404(Image, id=image_id)

    image.point_generation_method = \
        image.source.default_point_generation_method
    image.save()
    utils.generate_points(image, usesourcemethod=False)

    reset_features(image)

    messages.success(
        request, 'Reset image point generation method to source default.')
    return HttpResponseRedirect(reverse('image_detail', args=[image_id]))


@image_permission_required('image_id', perm=Source.PermTypes.EDIT.code)
@image_annotation_area_must_be_editable('image_id')
@require_POST
def image_reset_annotation_area(request, image_id):
    """
    Reset an image's annotation area to the source's default.
    This regenerates the image's points as well.
    """
    image = get_object_or_404(Image, id=image_id)

    image.metadata.annotation_area = image.source.image_annotation_area
    image.metadata.save()
    utils.generate_points(image, usesourcemethod=False)

    reset_features(image)

    messages.success(request, 'Reset annotation area to source default.')
    return HttpResponseRedirect(reverse('image_detail', args=[image_id]))


def import_groups(request, fileLocation):
    """
    Create label groups through a text file.
    NOTE: This method might be obsolete.
    """
    file = open(fileLocation, 'r') #opens the file for reading
    for line in file:
        line = line.replace("; ", ';')
        words = line.split(';')

        #creates a label object and stores it in the database
        group = LabelGroup(name=words[0], code=words[1])
        group.save()
    file.close()
