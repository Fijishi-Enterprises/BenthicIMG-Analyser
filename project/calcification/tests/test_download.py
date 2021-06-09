from django.urls import reverse

from export.tests.utils import BaseExportTest
from ..models import CalcifyRateTable


class RateTableDownloadTest(BaseExportTest):

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()

        cls.user = cls.create_user()
        cls.labels = cls.create_labels(cls.user, ['A', 'B', 'C'], 'GroupA')

    def test_basic(self):
        table = CalcifyRateTable(
            name="Table Name", description="Desc",
            rates_json={
                str(self.labels.get(name='A').pk): dict(
                    mean='2.0', lower_bound='1.0', upper_bound='3.0'),
                str(self.labels.get(name='B').pk): dict(
                    mean='-2.0', lower_bound='-3.0', upper_bound='-1.0'),
            },
            source=None)
        table.save()

        response = self.client.get(
            reverse('calcification:rate_table_download', args=[table.pk]))

        expected_lines = [
            'Label,Mean rate,Lower bound,Upper bound',
            'A,2.0,1.0,3.0',
            'B,-2.0,-3.0,-1.0',
        ]
        self.assert_csv_content_equal(response.content, expected_lines)

        self.assertEqual(
            response._headers['content-disposition'],
            ('Content-Disposition', 'attachment;filename="Table Name.csv"'),
            msg="CSV filename should be as expected")

    def test_table_name_with_non_filename_chars(self):
        table = CalcifyRateTable(
            name="<Table/Name?>", description="Desc",
            rates_json={},
            source=None)
        table.save()

        response = self.client.get(
            reverse('calcification:rate_table_download', args=[table.pk]))

        self.assertEqual(
            response._headers['content-disposition'],
            ('Content-Disposition', 'attachment;filename="_Table_Name__.csv"'),
            msg="CSV filename should replace expected chars with underscores")
