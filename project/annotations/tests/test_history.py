from __future__ import unicode_literals

from bs4 import BeautifulSoup
from django.urls import reverse

from images.model_utils import PointGen
from images.models import Source
from lib.tests.utils import ClientTest
from upload.tests.utils import UploadAnnotationsTestMixin


class AnnotationHistoryTest(ClientTest, UploadAnnotationsTestMixin):
    """
    Test the annotation history page.
    """
    # Assertion errors have the raw error followed by the
    # msg argument, if present.
    longMessage = True

    @classmethod
    def setUpTestData(cls):
        super(AnnotationHistoryTest, cls).setUpTestData()

        cls.user = cls.create_user()

        cls.source = cls.create_source(
            cls.user, visibility=Source.VisibilityTypes.PRIVATE,
            point_generation_type=PointGen.Types.SIMPLE,
            simple_number_of_points=3,
        )
        labels = cls.create_labels(cls.user, ['A', 'B'], 'GroupA')
        cls.create_labelset(cls.user, cls.source, labels)

        cls.user_outsider = cls.create_user()
        cls.user_viewer = cls.create_user()
        cls.add_source_member(
            cls.user, cls.source, cls.user_viewer, Source.PermTypes.VIEW.code)
        cls.user_editor = cls.create_user()
        cls.add_source_member(
            cls.user, cls.source, cls.user_editor, Source.PermTypes.EDIT.code)
        cls.user_editor2 = cls.create_user()
        cls.add_source_member(
            cls.user, cls.source, cls.user_editor2, Source.PermTypes.EDIT.code)

        cls.img = cls.upload_image(
            cls.user, cls.source,
            image_options=dict(filename='1.png'))

    def view_history(self, user):
        if user:
            self.client.force_login(user)
        else:
            self.client.logout()
        return self.client.get(
            reverse('annotation_history', args=[self.img.pk]))

    def assert_history_table_equals(self, response, expected_rows):
        response_soup = BeautifulSoup(response.content, 'html.parser')

        # History should be the SECOND detail table on this page, the first
        # having image aux metadata.
        # But it also might not exist at all.
        detail_table_soups = response_soup.find_all(
            'table', class_='detail_table')
        self.assertEqual(
            len(detail_table_soups), 2,
            msg="Unexpected number of detail tables on page")

        table_soup = detail_table_soups[1]
        row_soups = table_soup.find_all('tr')
        # Not checking the table's header row
        body_row_soups = row_soups[1:]

        # Check for equal number of rows
        self.assertEqual(
            len(expected_rows), len(body_row_soups),
            msg="History table doesn't have expected number of rows",
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

    def test_load_page_anonymous(self):
        """
        Load the page while logged out ->
        sorry, don't have permission.
        """
        response = self.view_history(None)
        self.assertStatusOK(response)
        self.assertTemplateUsed(response, self.PERMISSION_DENIED_TEMPLATE)

    def test_load_page_as_source_outsider(self):
        """
        Load the page as a user outside the source ->
        sorry, don't have permission.
        """
        response = self.view_history(self.user_outsider)
        self.assertStatusOK(response)
        self.assertTemplateUsed(response, self.PERMISSION_DENIED_TEMPLATE)

    def test_load_page_as_source_viewer(self):
        """
        Load the page as a source viewer ->
        sorry, don't have permission.
        """
        response = self.view_history(self.user_viewer)
        self.assertStatusOK(response)
        self.assertTemplateUsed(response, self.PERMISSION_DENIED_TEMPLATE)

    def test_load_page(self):
        response = self.view_history(self.user_editor)
        self.assertStatusOK(response)
        self.assertTemplateUsed(
            response, 'annotations/annotation_history.html')

    def test_access_event(self):
        # Access the annotation tool
        self.client.force_login(self.user)
        self.client.get(reverse('annotation_tool', args=[self.img.pk]))

        response = self.view_history(self.user)
        self.assert_history_table_equals(
            response,
            [
                ['Accessed annotation tool',
                 '{name}'.format(name=self.user.username)],
            ]
        )

    def test_human_annotation_event(self):
        data = dict(
            label_1='A', label_2='', label_3='B',
            robot_1='false', robot_2='false', robot_3='false',
        )
        self.client.force_login(self.user)
        self.client.post(
            reverse('save_annotations_ajax', args=[self.img.pk]), data)

        response = self.view_history(self.user)
        self.assert_history_table_equals(
            response,
            [
                ['Point 1: A<br/>Point 3: B',
                 '{name}'.format(name=self.user.username)],
            ]
        )

    def test_human_annotation_overwrite(self):
        # Annotate as user: 2 new (2 history points)
        data = dict(
            label_1='A', label_2='', label_3='B',
            robot_1='false', robot_2='false', robot_3='false',
        )
        self.client.force_login(self.user)
        self.client.post(
            reverse('save_annotations_ajax', args=[self.img.pk]), data)

        # Annotate as user_editor: 1 replaced, 1 new, 1 same (2 history points)
        data = dict(
            label_1='B', label_2='A', label_3='B',
            robot_1='false', robot_2='false', robot_3='false',
        )
        self.client.logout()
        self.client.force_login(self.user_editor)
        self.client.post(
            reverse('save_annotations_ajax', args=[self.img.pk]), data)

        response = self.view_history(self.user_editor)
        self.assert_history_table_equals(
            response,
            [
                # Remember, the table goes from newest to oldest entries
                ['Point 1: B<br/>Point 2: A',
                 '{name}'.format(name=self.user_editor.username)],
                ['Point 1: A<br/>Point 3: B',
                 '{name}'.format(name=self.user.username)],
            ]
        )

    def test_robot_annotation(self):
        robot = self.create_robot(self.source)
        self.add_robot_annotations(robot, self.img, {1: 'A', 2: 'B', 3: 'B'})

        response = self.view_history(self.user)
        self.assert_history_table_equals(
            response,
            [
                ['Point 1: A<br/>Point 2: B<br/>Point 3: B',
                 'Robot {ver}'.format(ver=robot.pk)],
            ]
        )

    def test_alleviate(self):
        self.source.confidence_threshold = 80
        self.source.save()

        robot = self.create_robot(self.source)
        self.add_robot_annotations(
            robot, self.img,
            {1: ('A', 81), 2: ('B', 79), 3: ('B', 95)})

        # Access the annotation tool to trigger Alleviate
        self.client.force_login(self.user)
        self.client.get(reverse('annotation_tool', args=[self.img.pk]))

        response = self.view_history(self.user)
        self.assert_history_table_equals(
            response,
            [
                # 3rd: Access event
                ['Accessed annotation tool',
                 '{name}'.format(name=self.user.username)],
                # 2nd: Alleviate should have triggered for points 1 and 3
                ['Point 1: A<br/>Point 3: B',
                 'Alleviate'],
                # 1st: Robot annotation
                ['Point 1: A<br/>Point 2: B<br/>Point 3: B',
                 'Robot {ver}'.format(ver=robot.pk)],
            ]
        )

    def test_csv_import(self):
        rows = [
            ['Name', 'Column', 'Row', 'Label'],
            ['1.png', 10, 10, 'A'],
            ['1.png', 20, 20, ''],
            ['1.png', 30, 30, 'B'],
        ]
        csv_file = self.make_csv_file('A.csv', rows)
        self.preview_csv_annotations(self.user, self.source, csv_file)
        self.upload_annotations(self.user, self.source)

        response = self.view_history(self.user)
        self.assert_history_table_equals(
            response,
            [
                ['Point 1: A<br/>Point 3: B', 'Imported'],
            ]
        )

    def test_cpc_import(self):
        cpc_files = [
            self.make_cpc_file(
                '1.cpc',
                r"C:\My Photos\2017-05-13 GBR\1.png", [
                    (9*15, 9*15, 'A'),
                    (19*15, 19*15, ''),
                    (29*15, 29*15, 'B')]),
        ]
        self.preview_cpc_annotations(self.user, self.source, cpc_files)
        self.upload_annotations(self.user, self.source)

        response = self.view_history(self.user)
        self.assert_history_table_equals(
            response,
            [
                ['Point 1: A<br/>Point 3: B', 'Imported'],
            ]
        )
