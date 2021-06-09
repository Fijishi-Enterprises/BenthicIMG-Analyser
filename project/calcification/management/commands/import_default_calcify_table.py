from collections import defaultdict

from django.core.management.base import BaseCommand, CommandError

from labels.models import Label
from upload.utils import csv_to_dict, text_file_to_unicode_stream
from ...models import CalcifyRateTable


class Command(BaseCommand):
    help = "Imports a default calcification rate table from CSV."

    def add_arguments(self, parser):

        parser.add_argument(
            'csv_path', type=str,
            help="Path to CSV file",
        )
        parser.add_argument(
            'name', type=str,
            help="Name to save for the table",
        )
        parser.add_argument(
            'description', type=str,
            help="Description to save for the table",
        )

    def handle(self, *args, **options):

        # CSV file to dict.

        with open(options['csv_path']) as csv_file:
            csv_unicode_stream = text_file_to_unicode_stream(csv_file)

        csv_data = csv_to_dict(
            csv_stream=csv_unicode_stream,
            required_columns=[
                ('label_name', "Label"),
                ('region', "Region"),
                ('mean', "Mean rate"),
                ('lower_bound', "Lower bound"),
                ('upper_bound', "Upper bound"),
            ],
            optional_columns=[],
            key_columns=['label_name', 'region'],
            multiple_rows_per_key=False,
        )

        # Convert to JSON:
        # label names to IDs, and one JSON structure per region.

        data_by_region = defaultdict(dict)

        for key, data in csv_data.items():
            label_name, region = key
            try:
                # Case insensitive name search
                label_id = Label.objects.get(name__iexact=label_name).pk
            except Label.DoesNotExist:
                raise CommandError(
                    "Label name not found: {}".format(label_name))
            data_by_region[region][label_id] = dict(
                mean=data['mean'],
                lower_bound=data['lower_bound'],
                upper_bound=data['upper_bound'],
            )

        # Print status and confirm to proceed.

        for region, data in data_by_region.items():
            region_label_count = len(data)
            self.stdout.write(
                f"Region '{region}' - {region_label_count} label(s)")

        input_text = input("Save tables to the database? [y/N]: ")

        # Must input 'y' or 'Y' to proceed. Else, will abort.
        if input_text.lower() != 'y':
            self.stdout.write("Aborting.")
            return

        # Save to database.

        for region, data in data_by_region.items():
            table = CalcifyRateTable(
                name=f"{options['name']} - {region}",
                description=options['description'],
                rates_json=data,
                source=None,
                region=region,
            )
            table.save()

        self.stdout.write("Saved tables to database.")
