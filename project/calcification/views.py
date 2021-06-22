import collections
import csv
import datetime
import re

from django.http import JsonResponse
from django.shortcuts import render
from django.template.loader import render_to_string
from django.views.decorators.http import require_GET, require_POST

from export.utils import create_csv_stream_response
from export.views import SourceCsvExportView
from images.models import Source
from lib.decorators import source_permission_required
from lib.exceptions import FileProcessError
from lib.forms import get_one_form_error
from upload.utils import text_file_to_unicode_stream
from .forms import CalcifyRateTableForm, ExportCalcifyStatsForm
from .models import CalcifyRateTable
from .utils import (
    get_default_calcify_tables, rate_table_csv_to_json, rate_table_json_to_csv)


@require_GET
def rate_table_download(request, table_id):
    """
    Download a calcification rate table as CSV.
    """
    def render_permission_error(request, message):
        return render(request, 'permission_denied.html', dict(error=message))

    table_permission_error_message = \
        f"You don't have permission to download table of ID {table_id}."

    try:
        rate_table = CalcifyRateTable.objects.get(pk=table_id)
    except CalcifyRateTable.DoesNotExist:
        # Technically the error message isn't accurate here, since it
        # implies the table ID exists. But users don't really have any
        # business knowing which table IDs exist or not outside their source.
        # So this obfuscation makes sense.
        return render_permission_error(request, table_permission_error_message)

    if rate_table.source:
        if not rate_table.source.visible_to_user(request.user):
            # Table belongs to a source, and the user doesn't have access to
            # that source.
            return render_permission_error(
                request, table_permission_error_message)

    # The source_id parameter tells us to limit the downloaded CSV to the
    # entries in the specified source's labelset, rather than including all
    # the rows of the rate table. This is particularly useful when downloading
    # a default rate table.
    if 'source_id' in request.GET:
        source_id = request.GET['source_id']
        source_permission_error_message = \
            f"You don't have permission to access source of ID {source_id}."

        try:
            source = Source.objects.get(pk=source_id)
        except Source.DoesNotExist:
            return render_permission_error(
                request, source_permission_error_message)

        if not source.visible_to_user(request.user):
            return render_permission_error(
                request, source_permission_error_message)
    else:
        source = None

    # At this point we do have permission, so proceed.

    # Convert the rate table's name to a valid filename in Windows and
    # Linux/Mac (or at least make a reasonable effort to).
    # Convert chars that are problematic in either OS to underscores.
    #
    # Linux only disallows / (and the null char, but we'll ignore that case).
    # Windows:
    # https://docs.microsoft.com/en-us/windows/win32/fileio/naming-a-file#naming-conventions
    non_filename_chars_regex = re.compile(r'[<>:"/\\|?*]')
    csv_filename = non_filename_chars_regex.sub('_', rate_table.name)

    # Make a CSV stream response and write the data to it.
    response = create_csv_stream_response('{}.csv'.format(csv_filename))
    rate_table_json_to_csv(response, rate_table, source=source)

    return response


class CalcifyStatsExportView(SourceCsvExportView):

    def get_export_filename(self, source):
        # Current date as YYYY-MM-DD
        current_date = datetime.datetime.now(
            datetime.timezone.utc).strftime('%Y-%m-%d')
        return f'{source.name} - Calcification rates - {current_date}.csv'

    def get_export_form(self, source, data):
        return ExportCalcifyStatsForm(source=source, data=data)

    def write_csv(self, response, source, image_set, export_form_data):

        calcify_rate_table = CalcifyRateTable.objects.get(
            pk=export_form_data['rate_table_id'])
        calcify_rates = calcify_rate_table.rates_json

        label_ids_to_names = {
            str(label['pk']): label['name']
            for label
            in source.labelset.get_globals().values('pk', 'name')
        }

        optional_columns = export_form_data['optional_columns']

        fieldnames = [
            "Image ID", "Image name",
            "Mean rate", "Lower bound", "Upper bound",
        ]
        if 'per_label_mean' in optional_columns:
            fieldnames.extend([
                f"{name} M" for name in label_ids_to_names.values()
            ])
        if 'per_label_bounds' in optional_columns:
            fieldnames.extend([
                f"{name} LB" for name in label_ids_to_names.values()
            ])
            fieldnames.extend([
                f"{name} UB" for name in label_ids_to_names.values()
            ])

        writer = csv.DictWriter(response, fieldnames)
        writer.writeheader()

        # Limit decimal places in the final numbers.
        def float_format(flt):
            # Always 3 decimal places (even if the trailing places are 0).
            s = format(flt, '.3f')
            if s == '-0.000':
                # Python has negative 0, but we don't care for that here.
                return '0.000'
            return s

        mean_rate_sum = 0
        lower_bound_sum = 0
        upper_bound_sum = 0
        mean_contribution_sums = collections.defaultdict(float)
        lower_bound_contribution_sums = collections.defaultdict(float)
        upper_bound_contribution_sums = collections.defaultdict(float)

        for image in image_set:

            # Counter for annotations of each label. Initialize by giving each
            # label a 0 count.
            label_counter = collections.Counter({
                label_id: 0
                for label_id in label_ids_to_names.keys()
            })

            annotation_labels = image.annotation_set.values_list(
                'label_id', flat=True)
            annotation_labels = [str(pk) for pk in annotation_labels]
            label_counter.update(annotation_labels)
            total = len(annotation_labels)

            row = {
                "Image ID": image.pk,
                "Image name": image.metadata.name,
            }
            image_mean_rate = 0
            image_lower_bound = 0
            image_upper_bound = 0

            for label_id, count in label_counter.items():

                if label_id in calcify_rates:
                    label_mean = float(calcify_rates[label_id]['mean'])
                    label_lower_bound = float(
                        calcify_rates[label_id]['lower_bound'])
                    label_upper_bound = float(
                        calcify_rates[label_id]['upper_bound'])
                else:
                    # Default to 0 (meaning, this label is assumed to have
                    # no net effect on calcification)
                    label_mean = 0
                    label_lower_bound = 0
                    label_upper_bound = 0

                if total > 0:
                    coverage = count / total
                else:
                    coverage = 0

                mean_contribution = coverage * label_mean
                lower_bound_contribution = coverage * label_lower_bound
                upper_bound_contribution = coverage * label_upper_bound

                image_mean_rate += mean_contribution
                image_lower_bound += lower_bound_contribution
                image_upper_bound += upper_bound_contribution

                label_name = label_ids_to_names[label_id]

                if 'per_label_mean' in optional_columns:

                    row[f"{label_name} M"] = float_format(mean_contribution)
                    mean_contribution_sums[label_name] += mean_contribution

                if 'per_label_bounds' in optional_columns:

                    row[f"{label_name} LB"] = float_format(
                        lower_bound_contribution)
                    row[f"{label_name} UB"] = float_format(
                        upper_bound_contribution)
                    lower_bound_contribution_sums[label_name] += \
                        lower_bound_contribution
                    upper_bound_contribution_sums[label_name] += \
                        upper_bound_contribution

            # Add image stats to CSV as fixed-places strings
            row["Mean rate"] = float_format(image_mean_rate)
            row["Lower bound"] = float_format(image_lower_bound)
            row["Upper bound"] = float_format(image_upper_bound)

            # Add to summary stats computation
            mean_rate_sum += image_mean_rate
            lower_bound_sum += image_lower_bound
            upper_bound_sum += image_upper_bound

            writer.writerow(row)

        num_images = image_set.count()
        if num_images <= 1:
            # Summary stats code ends up being a pain with 0 images, since we'd
            # have to catch division by 0 several times. Only bother with the
            # summary row if there are multiple images.
            return

        summary_row = {
            "Image ID": "ALL IMAGES",
            "Image name": "ALL IMAGES",
            "Mean rate": float_format(mean_rate_sum / num_images),
            "Lower bound": float_format(lower_bound_sum / num_images),
            "Upper bound": float_format(upper_bound_sum / num_images),
        }
        for _, label_name in label_ids_to_names.items():
            if 'per_label_mean' in optional_columns:
                summary_row[f"{label_name} M"] = float_format(
                    mean_contribution_sums[label_name] / num_images)
            if 'per_label_bounds' in optional_columns:
                summary_row[f"{label_name} LB"] = float_format(
                    lower_bound_contribution_sums[label_name] / num_images)
                summary_row[f"{label_name} UB"] = float_format(
                    upper_bound_contribution_sums[label_name] / num_images)
        writer.writerow(summary_row)


def response_after_table_upload_or_delete(request, source):
    """Helper function for upload and delete views."""

    # Re-render the rate table dropdown.
    blank_export_form = ExportCalcifyStatsForm(source=source)
    table_dropdown_html = str(blank_export_form['rate_table_id'])

    # Re-render the table-management grid.
    grid_of_tables_html = render_to_string(
        'calcification/grid_of_tables.html',
        dict(
            source_calcification_tables=source.calcifyratetable_set.order_by(
                'name'),
            default_calcification_tables=get_default_calcify_tables(),
            can_manage_calcification_tables=request.user.has_perm(
                Source.PermTypes.EDIT.code, source),
        ),
        # Passing the request gives us a RequestContext, which allows
        # rendering of the CSRF token.
        request,
    )

    # Return both in the Ajax response so they can be replaced via Javascript.
    return JsonResponse(dict(
        tableDropdownHtml=table_dropdown_html,
        gridOfTablesHtml=grid_of_tables_html,
    ))


@require_POST
@source_permission_required(
    'source_id', perm=Source.PermTypes.EDIT.code, ajax=True)
def rate_table_upload_ajax(request, source_id):
    """
    Upload a calcification rate table as CSV to the specified source.
    """
    source = Source.objects.get(pk=source_id)

    MAX_TABLE_COUNT = 5
    if source.calcifyratetable_set.count() >= MAX_TABLE_COUNT:
        return JsonResponse(dict(
            error=f"Up to {MAX_TABLE_COUNT} rate tables can be saved."
                  " You must delete a table before saving a new one."))

    form = CalcifyRateTableForm(source, request.POST, request.FILES)

    if not form.is_valid():
        # Find the first error and return it.
        return JsonResponse(dict(error=get_one_form_error(form)))

    # The above just checks for a valid CSV file. Now we process the CSV and
    # check that we can parse a rate table from it.
    try:
        rates_json = rate_table_csv_to_json(
            text_file_to_unicode_stream(form.cleaned_data['csv_file']))
    except FileProcessError as error:
        return JsonResponse(dict(
            error=str(error),
        ))

    # Save the table.
    table = CalcifyRateTable(
        name=form.cleaned_data['name'],
        description=form.cleaned_data['description'],
        rates_json=rates_json,
        source_id=source_id,
    )
    table.save()

    return response_after_table_upload_or_delete(request, source)


@require_POST
def rate_table_delete_ajax(request, table_id):
    """
    Delete a calcification rate table belonging to a source.
    """
    permission_error_message = \
        f"You don't have permission to delete table of ID {table_id}."

    try:
        rate_table = CalcifyRateTable.objects.get(pk=table_id)
    except CalcifyRateTable.DoesNotExist:
        # Technically the error message isn't accurate here, since it
        # implies the table ID exists. But users don't really have any
        # business knowing which table IDs exist or not outside their source.
        # So this obfuscation makes sense.
        return JsonResponse(dict(error=permission_error_message))

    if rate_table.source is None:
        # Can't delete default tables.
        return JsonResponse(dict(error=permission_error_message))

    if not request.user.has_perm(
            Source.PermTypes.EDIT.code, rate_table.source):
        # Don't have the proper permission to this source.
        return JsonResponse(dict(error=permission_error_message))

    # Do have permission.
    rate_table.delete()

    return response_after_table_upload_or_delete(request, rate_table.source)
