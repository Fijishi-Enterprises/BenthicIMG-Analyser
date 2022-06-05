from io import StringIO
from zipfile import ZipFile

from bs4.dammit import UnicodeDammit
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_GET, require_POST

from export.utils import get_request_images
from images.models import Source
from lib.decorators import (
    login_required_ajax,
    session_key_required,
    source_permission_required,
    source_labelset_required,
)
from lib.exceptions import FileProcessError
from lib.forms import get_one_form_error
from lib.utils import save_session_data
from upload.utils import annotations_preview, text_file_to_unicode_stream
from upload.views import AnnotationsUploadConfirmView
from .forms import CpcBatchEditForm, CpcImportForm, CpcExportForm
from .utils import (
    annotations_cpcs_to_dict,
    CpcFileContent,
    cpc_editor_csv_to_dicts,
    cpc_edit_labels,
    create_cpc_strings,
    create_zipped_cpcs_stream_response,
)


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
@require_POST
def upload_preview_ajax(request, source_id):
    """
    Add points/annotations to images by uploading Coral Point Count files.

    This view takes multiple .cpc files, processes them, saves the processed
    data to the session, and returns a preview table of the data to be saved.
    """
    source = get_object_or_404(Source, id=source_id)

    cpc_import_form = CpcImportForm(source, request.POST, request.FILES)
    if not cpc_import_form.is_valid():
        return JsonResponse(dict(
            error=cpc_import_form.errors['cpc_files'][0],
        ))

    try:
        cpc_info = annotations_cpcs_to_dict(
            cpc_import_form.get_cpc_names_and_streams(),
            source,
            cpc_import_form.cleaned_data['label_mapping'],
        )
    except FileProcessError as error:
        return JsonResponse(dict(
            error=str(error),
        ))

    annotations = dict((c['image_id'], c['annotations']) for c in cpc_info)
    preview_table, preview_details = \
        annotations_preview(annotations, source)

    cpc_files = dict(
        (c['image_id'],
         dict(filename=c['filename'], cpc_content=c['cpc_content']))
        for c in cpc_info
    )
    request.session['uploaded_annotations'] = annotations
    request.session['cpc_files'] = cpc_files

    return JsonResponse(dict(
        success=True,
        previewTable=preview_table,
        previewDetails=preview_details,
    ))


class CpcAnnotationsUploadConfirmView(AnnotationsUploadConfirmView):
    cpc_info = None

    def extra_source_level_actions(self, request, source):
        self.cpc_files = request.session.pop('cpc_files', None)

        # Save some defaults for future CPC exports. Here we get the code
        # filepath and image dir from any one of the uploaded CPCs.
        # Chances are they'll be the same for all uploaded CPCs, or they
        # might not - either way, this is just a default and doesn't have
        # to be perfect.
        image_id, cpc_file_dict = next(iter(self.cpc_files.items()))

        cpc = CpcFileContent.from_stream(
            StringIO(cpc_file_dict['cpc_content'], newline=''))

        source.cpce_code_filepath = cpc.code_filepath
        source.cpce_image_dir = cpc.get_image_dir(image_id)
        source.save()

    def update_image_and_metadata_fields(self, image, new_points):
        super().update_image_and_metadata_fields(image, new_points)

        # Save uploaded CPC contents for future CPC exports.
        # Note: Since cpc_files went through session serialization,
        # the integer dict keys became stringified.
        image.cpc_content = self.cpc_files[str(image.pk)]['cpc_content']
        image.cpc_filename = self.cpc_files[str(image.pk)]['filename']
        image.save()


@source_permission_required(
    'source_id', perm=Source.PermTypes.EDIT.code, ajax=True)
@require_POST
def export_prepare_ajax(request, source_id):
    """
    This is the first view after requesting a CPC export.
    Process the request fields, create the requested CPCs, and save them
    to the session. If there are any errors, report them with JSON.
    """
    source = get_object_or_404(Source, id=source_id)

    try:
        image_set, _ = get_request_images(request, source)
    except ValidationError as e:
        return JsonResponse(dict(
            error=e.message
        ))

    cpc_export_form = CpcExportForm(source, image_set, request.POST)
    if not cpc_export_form.is_valid():
        return JsonResponse(dict(
            error=get_one_form_error(cpc_export_form),
        ))

    cpc_prefs = cpc_export_form.cleaned_data
    # Create a dict of filenames to CPC-file-content strings
    cpc_strings = create_cpc_strings(image_set, cpc_prefs)
    # Save CPC prefs to the database for use next time
    source.cpce_code_filepath = cpc_prefs['local_code_filepath']
    source.cpce_image_dir = cpc_prefs['local_image_dir']
    source.save()

    session_key = save_session_data(
        request.session, 'cpc_export', cpc_strings)

    return JsonResponse(dict(
        session_key=session_key,
        success=True,
    ))


@source_permission_required('source_id', perm=Source.PermTypes.EDIT.code)
@require_GET
@session_key_required(
    error_redirect=['browse_images', 'source_id'],
    error_prefix="Export failed")
@transaction.non_atomic_requests
def export_serve(request, source_id, session_data):
    """
    This is the second view after requesting a CPC export.
    Grab the previously crafted CPCs from the session, and serve them in a
    zip file.
    """
    return create_zipped_cpcs_stream_response(
        session_data, 'annotations_cpc.zip')


@login_required
def cpc_batch_editor(request):
    return render(request, 'cpce/cpc_batch_editor.html', {
        'form': CpcBatchEditForm(),
    })


@login_required_ajax
@require_POST
def cpc_batch_editor_process_ajax(request):
    form = CpcBatchEditForm(request.POST, request.FILES)
    if not form.is_valid():
        return JsonResponse(dict(
            error=get_one_form_error(form),
        ))

    try:
        label_spec = cpc_editor_csv_to_dicts(
            text_file_to_unicode_stream(form.cleaned_data['label_spec_csv']))
    except FileProcessError as error:
        return JsonResponse(dict(
            error=str(error),
        ))

    zip_file = ZipFile(form.cleaned_data['cpc_zip'])
    cpc_strings = {}
    for filepath in zip_file.namelist():
        # Read in a cpc file
        cpc_raw = zip_file.read(filepath)
        cpc_string = UnicodeDammit(cpc_raw).unicode_markup
        # Edit the cpc file
        cpc_strings[filepath] = cpc_edit_labels(cpc_string, label_spec)

    session_key = save_session_data(
        request.session, 'cpc_batch_editor', cpc_strings)

    return JsonResponse(dict(
        session_key=session_key,
        success=True,
    ))


@login_required
@require_GET
@session_key_required(
    error_redirect='cpce:cpc_batch_editor',
    error_prefix="Batch edit failed")
def cpc_batch_editor_file_serve(request, session_data):
    return create_zipped_cpcs_stream_response(
        session_data, 'edited_cpcs.zip')
