import csv
from io import StringIO
import os
import tempfile

from lib.tests.utils import ManagementCommandTest
from ..models import CalcifyRateTable


class ImportDefaultTableTest(ManagementCommandTest):

    def test_success(self):

        # Set up data
        user = self.create_user()
        labels = self.create_labels(user, ['A', 'B'], 'GroupA')

        # Set up CSV contents
        stream = StringIO()
        columns = [
            "Label", "Region", "Mean rate", "Lower bound", "Upper bound"]
        writer = csv.DictWriter(stream, columns)
        writer.writeheader()
        writer.writerow({
            'Label': 'A',
            'Region': 'Indo-Pacific',
            'Mean rate': '2.0',
            'Lower bound': '1.0',
            'Upper bound': '3.0',
        })
        writer.writerow({
            # Should be case insensitive
            'Label': 'a',
            'Region': 'Atlantic',
            'Mean rate': '5.0',
            'Lower bound': '4.0',
            'Upper bound': '7.0',
        })
        writer.writerow({
            'Label': 'B',
            'Region': 'Indo-Pacific',
            'Mean rate': '-2.0',
            'Lower bound': '-3.0',
            'Upper bound': '-1.0',
        })
        csv_contents = stream.getvalue()

        with tempfile.NamedTemporaryFile(
                mode='w', newline='', suffix='.csv', delete=False) as csv_file:

            # Write CSV.
            csv_file.write(csv_contents)
            # The command opens the file from the pathname, so close it first.
            csv_file.close()

            args = [csv_file.name, "Name goes here", "Description goes here"]
            stdout_text, _ = self.call_command_and_get_output(
                'calcification', 'import_default_calcify_table', args=args)

            os.remove(csv_file.name)

        # Verify output
        self.assertIn("Region 'Indo-Pacific' - 2 label(s)", stdout_text)
        self.assertIn("Region 'Atlantic' - 1 label(s)", stdout_text)

        # Verify database content

        indo_pacific_table = CalcifyRateTable.objects.get(
            region="Indo-Pacific", source__isnull=True)
        self.assertEqual(
            indo_pacific_table.name, "Name goes here - Indo-Pacific")
        self.assertEqual(
            indo_pacific_table.description, "Description goes here")
        self.assertDictEqual(
            indo_pacific_table.rates_json,
            {
                str(labels.get(name='A').pk): dict(
                    mean='2.0', lower_bound='1.0', upper_bound='3.0'),
                str(labels.get(name='B').pk): dict(
                    mean='-2.0', lower_bound='-3.0', upper_bound='-1.0'),
            }
        )

        atlantic_table = CalcifyRateTable.objects.get(
            region="Atlantic", source__isnull=True)
        self.assertEqual(
            atlantic_table.name, "Name goes here - Atlantic")
        self.assertEqual(
            atlantic_table.description, "Description goes here")
        self.assertDictEqual(
            atlantic_table.rates_json,
            {
                str(labels.get(name='A').pk): dict(
                    mean='5.0', lower_bound='4.0', upper_bound='7.0'),
            }
        )

    # TODO:
    # - Test nonexistent label case.
    # - Test invalid CSV file case (might have to add code to handle this too).
