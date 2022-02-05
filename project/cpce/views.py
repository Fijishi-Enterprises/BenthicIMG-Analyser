from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse

from export.utils import get_request_images
from images.models import Source
from lib.decorators import source_permission_required, source_labelset_required
from lib.exceptions import FileProcessError
from lib.forms import get_one_form_error
from upload.utils import annotations_preview
from upload.views import AnnotationsUploadConfirmView
from .forms import CpcImportForm, CpcPrefsForm
from .utils import (
    annotations_cpcs_to_dict, create_cpc_strings,
    create_zipped_cpcs_stream_response)


@source_permission_required('source_id', perm=Source.PermTypes.EDIT.code)
@source_labelset_required('source_id', message=(
    "You must create a labelset before uploading annotations."))
def upload_page(request, source_id):
    source = get_object_or_404(Source, id=source_id)

    cpc_import_form = CpcImportForm(source)

    return render(request, 'cpce/upload.html', {
        'source': source,
        'cpc_import_form': cpc_import_form,
    })


@source_permission_required(
    'source_id', perm=Source.PermTypes.EDIT.code, ajax=True)
@source_labelset_required('source_id', message=(
    "You must create a labelset before uploading annotations."))
def upload_preview_ajax(request, source_id):
    """
    Add points/annotations to images by uploading Coral Point Count files.

    This view takes multiple .cpc files, processes them, saves the processed
    data to the session, and returns a preview table of the data to be saved.
    """
    if request.method != 'POST':
        return JsonResponse(dict(
            error="Not a POST request",
        ))

    source = get_object_or_404(Source, id=source_id)

    cpc_import_form = CpcImportForm(source, request.POST, request.FILES)
    if not cpc_import_form.is_valid():
        return JsonResponse(dict(
            error=cpc_import_form.errors['cpc_files'][0],
        ))

    try:
        cpc_info = annotations_cpcs_to_dict(
            cpc_import_form.get_cpc_names_and_streams(), source,
            cpc_import_form.cleaned_data['plus_notes'])
    except FileProcessError as error:
        return JsonResponse(dict(
            error=str(error),
        ))

    preview_table, preview_details = \
        annotations_preview(cpc_info['annotations'], source)

    request.session['uploaded_annotations'] = cpc_info['annotations']
    request.session['cpc_info'] = cpc_info

    return JsonResponse(dict(
        success=True,
        previewTable=preview_table,
        previewDetails=preview_details,
    ))


class CpcAnnotationsUploadConfirmView(AnnotationsUploadConfirmView):
    cpc_info = None

    def extra_source_level_actions(self, request, source):
        self.cpc_info = request.session.pop('cpc_info', None)

        # We uploaded annotations as CPC. Save some info for future CPC
        # exports.
        source.cpce_code_filepath = self.cpc_info['code_filepath']
        source.cpce_image_dir = self.cpc_info['image_dir']
        source.save()

    def update_image_and_metadata_fields(self, image, new_points):
        super().update_image_and_metadata_fields(image, new_points)

        # Save uploaded CPC contents for future CPC exports.
        # Note: Since cpc_info went through session serialization,
        # dicts with integer keys have had their keys stringified.
        image.cpc_content = self.cpc_info['cpc_contents'][str(image.pk)]
        image.cpc_filename = self.cpc_info['cpc_filenames'][str(image.pk)]
        image.save()


@source_permission_required(
    'source_id', perm=Source.PermTypes.EDIT.code, ajax=True)
def export_prepare_ajax(request, source_id):
    """
    This is the first view after requesting a CPC export.
    Process the request fields, create the requested CPCs, and save them
    to the session. If there are any errors, report them with JSON.
    """
    if request.method != 'POST':
        return JsonResponse(dict(
            error="Not a POST request",
        ))

    source = get_object_or_404(Source, id=source_id)

    try:
        image_set, _ = get_request_images(request, source)
    except ValidationError as e:
        return JsonResponse(dict(
            error=e.message
        ))

    cpc_prefs_form = CpcPrefsForm(source, request.POST)
    if not cpc_prefs_form.is_valid():
        return JsonResponse(dict(
            error=get_one_form_error(cpc_prefs_form),
        ))

    cpc_prefs = cpc_prefs_form.cleaned_data
    # Create a dict of filenames to CPC-file-content strings
    cpc_strings = create_cpc_strings(image_set, cpc_prefs)
    # Save CPC strings to the session
    request.session['cpc_strings'] = cpc_strings
    # Save CPC prefs to the database for use next time
    source.cpce_code_filepath = cpc_prefs['local_code_filepath']
    source.cpce_image_dir = cpc_prefs['local_image_dir']
    source.save()

    return JsonResponse(dict(
        success=True,
    ))


@source_permission_required('source_id', perm=Source.PermTypes.EDIT.code)
@transaction.non_atomic_requests
def export_serve(request, source_id):
    """
    This is the second view after requesting a CPC export.
    Grab the previously crafted CPCs from the session, and serve them in a
    zip file.
    The only reason this view really exists (instead of being merged with the
    other CPC export view) is that a file download seemingly needs to be
    non-Ajax.
    """
    cpc_strings = request.session.pop('cpc_strings', None)
    if not cpc_strings:
        messages.error(
            request,
            (
                "Export failed; we couldn't find the expected data in"
                " your session."
                " Please try the export again. If the problem persists,"
                " let us know on the forum."
            ),
        )
        return HttpResponseRedirect(
            reverse('browse_images', args=[source_id]))

    response = create_zipped_cpcs_stream_response(
        cpc_strings, 'annotations_cpc.zip')

    return response
