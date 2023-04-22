from bs4 import BeautifulSoup
from django.urls import reverse


class AnnotationHistoryTestMixin:

    def view_history(self, user, img=None):
        if user:
            self.client.force_login(user)
        else:
            self.client.logout()

        if img is None:
            img = self.img
        return self.client.get(
            reverse('annotation_history', args=[img.pk]))

    def assert_history_table_equals(self, response, expected_rows):
        response_soup = BeautifulSoup(response.content, 'html.parser')

        # History should be the SECOND detail table on this page, the first
        # having image aux metadata.
        # But if there's no history, the table won't be there at all.
        detail_table_soups = response_soup.find_all(
            'table', class_='detail_table')

        if expected_rows == []:
            self.assertEqual(
                len(detail_table_soups), 1,
                msg="History table shouldn't be present")
            return

        self.assertEqual(
            len(detail_table_soups), 2,
            msg="Should have two detail tables on page")

        table_soup = detail_table_soups[1]
        row_soups = table_soup.find_all('tr')
        # Not checking the table's header row
        body_row_soups = row_soups[1:]

        # Check for equal number of rows
        self.assertEqual(
            len(expected_rows), len(body_row_soups),
            msg="History table should have expected number of rows",
        )

        # Check that row content matches what we expect
        for row_num, row_soup in enumerate(body_row_soups, 1):
            expected_row = expected_rows[row_num - 1]
            cell_soups = row_soup.find_all('td')
            # Point numbers and label codes
            expected_cell = '<td>' + expected_row[0] + '</td>'
            self.assertHTMLEqual(
                expected_cell, str(cell_soups[0]),
                msg="Point/label mismatch in row {n}".format(n=row_num),
            )
            # Annotator
            expected_cell = '<td>' + expected_row[1] + '</td>'
            self.assertHTMLEqual(
                expected_cell, str(cell_soups[1]),
                msg="Annotator mismatch in row {n}".format(n=row_num),
            )
            # Date; we may or may not care about checking this
            if len(expected_row) > 2:
                expected_cell = '<td>' + expected_row[2] + '</td>'
                self.assertHTMLEqual(
                    expected_cell, str(cell_soups[2]),
                    msg="Date mismatch in row {n}".format(n=row_num),
                )
