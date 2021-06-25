import collections
import csv

from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views import View

from .forms import CpcPrefsForm, ExportAnnotationsForm, ExportImageCoversForm
from .utils import create_cpc_strings, \
    create_csv_stream_response, \
    create_zipped_cpcs_stream_response, get_request_images, \
    write_annotations_csv, write_labelset_csv
from images.models import Source
from images.utils import metadata_field_names_to_labels
from lib.decorators import source_permission_required, \
    source_visibility_required
from lib.forms import get_one_form_error


# TODO: Use this View class to improve DRY among more of the export views.

decorators = [
    # Access control.
    source_visibility_required('source_id'),
    # These exports can be resource intensive, so no bots allowed.
    login_required,
    # This is a potentially slow view that doesn't modify the database,
    # so don't open a transaction for the view.
    transaction.non_atomic_requests]
@method_decorator(decorators, name='dispatch')
class SourceCsvExportView(View):
    """
    Data export on a subset of an source's images.
    """
    def get_export_filename(self, source):
        raise NotImplementedError

    def get_export_form(self, source, data):
        raise NotImplementedError

    def write_csv(self, response, source, image_set, export_form_data):
        raise NotImplementedError

    def post(self, request, source_id):
        """
        We define these views as POST, not GET, because we want to save
        database stats for some of the source-level exports.

        Also, none of the advantages of GET particularly apply to these
        export views (bookmarking the URL, bots indexing the response,
        avoiding browser resend warnings on Back/Refresh, etc.)
        """
        source = get_object_or_404(Source, id=source_id)

        try:
            image_set = get_request_images(request, source)
        except ValidationError as e:
            messages.error(request, e.message)
            return HttpResponseRedirect(
                reverse('browse_images', args=[source_id]))

        export_form = self.get_export_form(source, request.POST)
        if not export_form.is_valid():
            messages.error(request, get_one_form_error(export_form))
            return HttpResponseRedirect(
                reverse('browse_images', args=[source_id]))

        filename = self.get_export_filename(source)
        response = create_csv_stream_response(filename)

        self.write_csv(response, source, image_set, export_form.cleaned_data)

        return response


class ImageStatsExportView(SourceCsvExportView):
    """
    Stats export where each row pertains to a single image's annotation data.
    """

    def finish_fieldnames_and_image_loop_prep(
            self, fieldnames, export_form_data):
        raise NotImplementedError

    def image_loop_main_body(
            self, row, label_counter, num_annotations_in_image):
        raise NotImplementedError

    def finish_summary_row(self, summary_row, num_annotated_images):
        raise NotImplementedError

    @staticmethod
    def float_format(flt):
        """Limit decimal places in the CSV's final numbers."""

        # Always 3 decimal places (even if the trailing places are 0).
        s = format(flt, '.3f')
        if s == '-0.000':
            # Python has negative 0, but we don't care for that here.
            return '0.000'
        return s

    def write_csv(self, response, source, image_set, export_form_data):

        # Make a dict of global label IDs to string displays for the
        # source's labelset. The form of the string display depends on the
        # export form's data.
        # The dict is ordered by functional group and then name/code
        # (note that regular dicts remember insertion order in Python 3.6+).
        if export_form_data['label_display'] == 'name':
            self.label_ids_to_displays = {
                global_label.pk: global_label.name
                for global_label
                in source.labelset.get_globals().order_by('group', 'name')
            }
        else:
            # 'code'
            self.label_ids_to_displays = {
                local_label.global_label.pk: local_label.code
                for local_label
                in source.labelset.get_locals_ordered_by_group_and_code()
            }

        # Header row.
        fieldnames = ["Image ID", "Image name", "Annotation status", "Points"]
        fieldnames = self.finish_fieldnames_and_image_loop_prep(
            fieldnames, export_form_data)

        num_annotated_images = 0

        writer = csv.DictWriter(response, fieldnames)
        writer.writeheader()

        # One row per image
        for image in image_set:

            if image.get_annotation_status_code() == 'needs_annotation':
                # The image is unannotated or partially annotated, so chances
                # are it won't be useful to export, and it'll skew the summary
                # stats as well. Skip the image.
                continue
            num_annotated_images += 1

            # Counter for annotations of each label. Initialize by giving each
            # label a 0 count.
            label_counter = collections.Counter({
                label_id: 0
                for label_id in self.label_ids_to_displays.keys()
            })

            annotation_labels = image.annotation_set.values_list(
                'label_id', flat=True)
            annotation_labels = [pk for pk in annotation_labels]
            label_counter.update(annotation_labels)
            num_annotations_in_image = len(annotation_labels)

            row = {
                "Image ID": image.pk,
                "Image name": image.metadata.name,
                "Annotation status": image.get_annotation_status_str(),
                "Points": image.point_set.count(),
            }
            row = self.image_loop_main_body(
                row, label_counter, num_annotations_in_image)
            writer.writerow(row)

        if num_annotated_images <= 1:
            # Summary stats code ends up being a pain with 0 images, since we'd
            # have to catch division by 0 several times.
            # Also, we only need to bother with the summary row
            # if there are multiple annotated images.
            return

        summary_row = {
            "Image ID": "ALL IMAGES",
            "Image name": "",
            "Annotation status": "",
            "Points": "",
        }
        summary_row = self.finish_summary_row(summary_row, num_annotated_images)
        writer.writerow(summary_row)


@source_visibility_required('source_id')
@login_required
@transaction.non_atomic_requests
def export_metadata(request, source_id):
    source = get_object_or_404(Source, id=source_id)

    try:
        image_set = get_request_images(request, source)
    except ValidationError as e:
        messages.error(request, e.message)
        return HttpResponseRedirect(
            reverse('browse_images', args=[source_id]))

    response = create_csv_stream_response('metadata.csv')
    writer = csv.writer(response)

    # Get the metadata fields that we'll write CSV for.
    field_names_to_labels = metadata_field_names_to_labels(source)

    # Header row
    writer.writerow(field_names_to_labels.values())

    # Metadata, one row per image
    for image in image_set:
        row = []
        for field_name in field_names_to_labels.keys():
            # Use getattr on the Metadata model object to get the
            # metadata values. If the value is None, write ''.
            value = getattr(image.metadata, field_name)
            if value is None:
                value = ''
            row.append(value)
        writer.writerow(row)

    return response


@source_visibility_required('source_id')
@login_required
@transaction.non_atomic_requests
def export_annotations(request, source_id):
    source = get_object_or_404(Source, id=source_id)

    try:
        image_set = get_request_images(request, source)
    except ValidationError as e:
        messages.error(request, e.message)
        return HttpResponseRedirect(
            reverse('browse_images', args=[source_id]))

    export_annotations_form = ExportAnnotationsForm(request.POST)
    if not export_annotations_form.is_valid():
        messages.error(request, get_one_form_error(export_annotations_form))
        return HttpResponseRedirect(
            reverse('browse_images', args=[source_id]))

    response = create_csv_stream_response('annotations.csv')

    write_annotations_csv(
        response, source, image_set,
        export_annotations_form.cleaned_data['optional_columns'])

    return response


@source_permission_required(
    'source_id', perm=Source.PermTypes.EDIT.code, ajax=True)
def export_annotations_cpc_create_ajax(request, source_id):
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
        image_set = get_request_images(request, source)
    except ValidationError as e:
        return JsonResponse(dict(
            error=e.message
        ))

    cpc_prefs_form = CpcPrefsForm(request.POST)
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
def export_annotations_cpc_serve(request, source_id):
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


class ImageCoversExportView(ImageStatsExportView):

    def get_export_filename(self, source):
        return 'percent_covers.csv'

    def get_export_form(self, source, data):
        return ExportImageCoversForm(data)

    def finish_fieldnames_and_image_loop_prep(
            self, fieldnames, export_form_data):

        # One column per label
        fieldnames.extend(self.label_ids_to_displays.values())

        self.coverage_sums = collections.defaultdict(float)

        return fieldnames

    def image_loop_main_body(
            self, row, label_counter, num_annotations_in_image):

        for label_id, count in label_counter.items():

            label_display = self.label_ids_to_displays[label_id]

            coverage_fraction = count / num_annotations_in_image
            coverage_percent_str = self.float_format(
                coverage_fraction * 100.0)
            row[label_display] = coverage_percent_str

            # Add to summary stats computation
            self.coverage_sums[label_display] += coverage_fraction

        return row

    def finish_summary_row(self, summary_row, num_annotated_images):

        for label_display in self.label_ids_to_displays.values():
            summary_row[label_display] = self.float_format(
                100.0 * self.coverage_sums[label_display]
                / num_annotated_images)

        return summary_row


@source_visibility_required('source_id')
@transaction.non_atomic_requests
def export_labelset(request, source_id):
    source = get_object_or_404(Source, id=source_id)

    response = create_csv_stream_response('labelset.csv')
    writer = csv.writer(response)
    write_labelset_csv(writer, source)

    return response
