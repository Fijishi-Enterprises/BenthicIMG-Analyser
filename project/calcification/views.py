from collections import Counter
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

        for image in image_set:

            # Counter for annotations of each label. Initialize by giving each
            # label a 0 count.
            label_counter = Counter({
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
                "Mean rate": 0,
                "Lower bound": 0,
                "Upper bound": 0,
            }

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

                row["Mean rate"] += mean_contribution
                row["Lower bound"] += lower_bound_contribution
                row["Upper bound"] += upper_bound_contribution

                label_name = label_ids_to_names[label_id]

                if 'per_label_mean' in optional_columns:
                    row[f"{label_name} M"] = float_format(mean_contribution)
                if 'per_label_bounds' in optional_columns:
                    row[f"{label_name} LB"] = float_format(
                        lower_bound_contribution)
                    row[f"{label_name} UB"] = float_format(
                        upper_bound_contribution)

            row["Mean rate"] = float_format(row["Mean rate"])
            row["Lower bound"] = float_format(row["Lower bound"])
            row["Upper bound"] = float_format(row["Upper bound"])

            writer.writerow(row)
