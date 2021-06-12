import collections
import csv
import datetime
import re

from django.shortcuts import get_object_or_404

from export.utils import create_csv_stream_response
from export.views import SourceCsvExportView
from .forms import ExportCalcifyStatsForm
from .models import CalcifyRateTable
from .utils import rate_table_json_to_csv


# TODO: Whenever we implement saving user-defined tables: If the table belongs to a source, require permission to that source.
def rate_table_download(request, table_id):
    """
    Main page for a particular label
    """
    rate_table = get_object_or_404(CalcifyRateTable, id=table_id)

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
    rate_table_json_to_csv(response, rate_table)

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
