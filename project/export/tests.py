from __future__ import unicode_literals
from zipfile import ZipFile
from six import BytesIO, StringIO

from django.core.files.base import ContentFile
from django.core.urlresolvers import reverse

from .utils import get_previous_cpcs_status, write_zip
from images.model_utils import PointGen
from images.models import Image
from lib.test_utils import ClientTest


class CPCExportTest(ClientTest):

    @classmethod
    def setUpTestData(cls):
        super(CPCExportTest, cls).setUpTestData()

        cls.user = cls.create_user()
        cls.source = cls.create_source(
            cls.user,
            point_generation_type=PointGen.Types.UNIFORM,
            number_of_cell_rows=2, number_of_cell_columns=3,
            min_x=5, max_x=95, min_y=10, max_y=90,
            confidence_threshold=80,
        )
        labels = cls.create_labels(cls.user, ['A', 'B'], 'GroupA')
        cls.create_labelset(cls.user, cls.source, labels)

        cls.img1 = cls.upload_image(
            cls.user, cls.source,
            dict(filename='1.jpg', width=400, height=300))
        cls.img2 = cls.upload_image(cls.user, cls.source)

        # Due to using uniform-grid points, we know the point positions
        img1_point_positions = [
            (78, 88), (198, 88), (319, 88),
            (78, 209), (198, 209), (319, 209),
        ]
        cls.img1_cpc_point_positions = [
            str(x*15) + ',' + str(y*15) for x, y in img1_point_positions]

        # Image search parameters
        cls.default_search_params = dict(
            image_form_type='search',
            aux1='', aux2='', aux3='', aux4='', aux5='',
            height_in_cm='', latitude='', longitude='', depth='',
            photographer='', framing='', balance='',
            date_filter_0='year', date_filter_1='',
            date_filter_2='', date_filter_3='',
            annotation_status='',
        )

    def export_cpcs(self, post_data):
        """
        :param post_data: The POST data for the CPC-creation Ajax view.
        :return: The response object from the CPC-serving view. Should be a
          zip file raw string if the view ran without errors.
        """
        self.client.force_login(self.user)
        self.client.post(
            reverse(
                'export_annotations_cpc_create_ajax', args=[self.source.pk]),
            post_data,
        )
        return self.client.post(
            reverse('export_annotations_cpc_serve', args=[self.source.pk])
        )

    @staticmethod
    def export_response_to_cpc(response, cpc_filename):
        zf = ZipFile(StringIO(response.content))
        return zf.read(cpc_filename)

    def upload_cpcs(self, cpc_files):
        self.client.force_login(self.user)
        self.client.post(
            reverse(
                'upload_annotations_cpc_preview_ajax', args=[self.source.pk]),
            {'cpc_files': cpc_files},
        )
        self.client.post(
            reverse('upload_annotations_ajax', args=[self.source.pk]),
        )

    def assert_cpc_content_equal(self, actual_cpc_content, expected_lines):
        """
        :param actual_cpc_content: CPC content from the export view's response.
        :param expected_lines: List of strings, without newline characters,
          representing the expected line contents. Note that this is a
          different format from actual_cpc_content, just because it's easier
          to type non-newline strings in Python code.
        Throws AssertionError if actual and expected CPCs are not equal.
        """
        actual_lines = actual_cpc_content.splitlines()

        # Yes, CPCe does put a newline at the end
        expected_cpc_content = '\r\n'.join(expected_lines) + '\r\n'

        # Compare individual lines (so that if we get a mismatch, the error
        # message will be readable)
        for line_num, actual_line in enumerate(actual_lines, 1):
            expected_line = expected_lines[line_num-1]
            self.assertEqual(actual_line, expected_line, msg=(
                "Line {line_num} not equal | Actual: {actual_line}"
                " | Expected: {expected_line}").format(
                line_num=line_num, actual_line=actual_line,
                expected_line=expected_line,
            ))
        # Compare entire file (to ensure line separator types are correct too)
        self.assertEqual(actual_cpc_content, expected_cpc_content)

    def test_write_from_scratch(self):
        # Add some annotations
        self.add_annotations(
            self.user, self.img1, {1: 'A', 2: 'B', 3: 'A', 4: 'A'})

        # Export, and get exported CPC content
        post_data = self.default_search_params.copy()
        post_data.update(
            # CPC prefs
            local_code_filepath=r'C:\CPCe codefiles\My codes.txt',
            local_image_dir=r'C:\Panama dataset',
            annotation_filter='confirmed_only',
        )
        response = self.export_cpcs(post_data)
        actual_cpc_content = self.export_response_to_cpc(response, '1.cpc')

        # This is what we expect to get in our export
        expected_lines = [
            (r'"C:\CPCe codefiles\My codes.txt",'
             r'"C:\Panama dataset\1.jpg",6000,4500,14400,10800'),
            '285,4035',
            '5685,4035',
            '5685,435',
            '285,435',
            '6',
            self.img1_cpc_point_positions[0],
            self.img1_cpc_point_positions[1],
            self.img1_cpc_point_positions[2],
            self.img1_cpc_point_positions[3],
            self.img1_cpc_point_positions[4],
            self.img1_cpc_point_positions[5],
            '"1","A","Notes",""',
            '"2","B","Notes",""',
            '"3","A","Notes",""',
            '"4","A","Notes",""',
            '"5","","Notes",""',
            '"6","","Notes",""',
        ]
        expected_lines.extend(['" "']*28)

        self.assert_cpc_content_equal(actual_cpc_content, expected_lines)

    def test_write_based_on_prev_cpc(self):
        cpc_lines = [
            (r'"C:\CPCe codefiles\My codes.txt",'
             r'"C:\Panama dataset\1.jpg",6000,4500,20000,25000'),
            '285,4035',
            '5685,4035',
            '5685,435',
            '285,435',
            # Different number of points from the source's default
            '2',
            self.img1_cpc_point_positions[2],
            self.img1_cpc_point_positions[3],
            # Include notes codes
            '"1","A","Notes","AC"',
            '"2","","Notes","BD"',
        ]
        # Add some non-blank header values
        cpc_lines.extend(['"Header value goes here"']*28)
        # Yes, CPCe does put a newline at the end
        cpc_content = '\r\n'.join(cpc_lines) + '\r\n'

        # Upload with a CPC filename different from the image filename
        f = ContentFile(cpc_content, name='Panama_1.cpc')
        self.upload_cpcs([f])

        # Change some annotations; we expect the CPC file to be the same
        # except for the changed labels. Notes codes should be preserved.
        annotations = {1: 'B', 2: 'A'}
        self.add_annotations(self.user, self.img1, annotations)
        expected_lines = cpc_lines[:]
        expected_lines[8] = '"1","B","Notes","AC"'
        expected_lines[9] = '"2","A","Notes","BD"'

        # Export, and get exported CPC content
        post_data = self.default_search_params.copy()
        post_data.update(
            # CPC prefs
            local_code_filepath=r'C:\CPCe codefiles\My codes.txt',
            local_image_dir=r'C:\Panama dataset',
            annotation_filter='confirmed_only',
        )
        response = self.export_cpcs(post_data)
        actual_cpc_content = self.export_response_to_cpc(
            response, 'Panama_1.cpc')

        self.assert_cpc_content_equal(actual_cpc_content, expected_lines)

    def test_from_scratch_confirmed_only(self):
        """
        No previous CPC upload; requesting confirmed annotations only.
        """
        self.add_robot_annotations(
            self.create_robot(self.source), self.img1,
            {1: ('B', 90), 2: ('B', 70),
             3: ('B', 60), 4: ('B', 79), 5: ('B', 81), 6: ('B', 99)})
        # Only these should count
        self.add_annotations(
            self.user, self.img1, {1: 'A', 2: 'A'})

        # Export, and get exported CPC content
        post_data = self.default_search_params.copy()
        post_data.update(
            # CPC prefs
            local_code_filepath=r'C:\CPCe codefiles\My codes.txt',
            local_image_dir=r'C:\Panama dataset',
            annotation_filter='confirmed_only',
        )
        response = self.export_cpcs(post_data)
        actual_cpc_content = self.export_response_to_cpc(response, '1.cpc')

        # This is what we expect to get in our export
        expected_lines = [
            (r'"C:\CPCe codefiles\My codes.txt",'
             r'"C:\Panama dataset\1.jpg",6000,4500,14400,10800'),
            '285,4035',
            '5685,4035',
            '5685,435',
            '285,435',
            '6',
            self.img1_cpc_point_positions[0],
            self.img1_cpc_point_positions[1],
            self.img1_cpc_point_positions[2],
            self.img1_cpc_point_positions[3],
            self.img1_cpc_point_positions[4],
            self.img1_cpc_point_positions[5],
            # Should ONLY have human annotations
            '"1","A","Notes",""',
            '"2","A","Notes",""',
            '"3","","Notes",""',
            '"4","","Notes",""',
            '"5","","Notes",""',
            '"6","","Notes",""',
        ]
        expected_lines.extend(['" "']*28)

        self.assert_cpc_content_equal(actual_cpc_content, expected_lines)

    def test_from_scratch_with_unconfirmed_confident(self):
        """
        No previous CPC upload; including unconfirmed confident annotations.
        """
        # Add robot annotations, some confident and some not (threshold 80,
        # so >= 80 is confident). We're dealing with floats in general, so
        # don't test EXACTLY 80 or it'll be finicky.
        self.add_robot_annotations(
            self.create_robot(self.source), self.img1,
            {1: ('B', 90), 2: ('B', 70),
             3: ('B', 60), 4: ('B', 79), 5: ('B', 81), 6: ('B', 99)})
        # Add human annotations, with at least one overwriting an
        # unconfirmed confident annotation
        self.add_annotations(
            self.user, self.img1, {1: 'A', 2: 'A'})

        # Export, and get exported CPC content
        post_data = self.default_search_params.copy()
        post_data.update(
            # CPC prefs
            local_code_filepath=r'C:\CPCe codefiles\My codes.txt',
            local_image_dir=r'C:\Panama dataset',
            annotation_filter='confirmed_and_confident',
        )
        response = self.export_cpcs(post_data)
        actual_cpc_content = self.export_response_to_cpc(response, '1.cpc')

        # This is what we expect to get in our export
        expected_lines = [
            (r'"C:\CPCe codefiles\My codes.txt",'
             r'"C:\Panama dataset\1.jpg",6000,4500,14400,10800'),
            '285,4035',
            '5685,4035',
            '5685,435',
            '285,435',
            '6',
            self.img1_cpc_point_positions[0],
            self.img1_cpc_point_positions[1],
            self.img1_cpc_point_positions[2],
            self.img1_cpc_point_positions[3],
            self.img1_cpc_point_positions[4],
            self.img1_cpc_point_positions[5],
            # 1 and 2 are confirmed, 3-4 non-confident, 5-6 confident
            '"1","A","Notes",""',
            '"2","A","Notes",""',
            '"3","","Notes",""',
            '"4","","Notes",""',
            '"5","B","Notes",""',
            '"6","B","Notes",""',
        ]
        expected_lines.extend(['" "']*28)

        self.assert_cpc_content_equal(actual_cpc_content, expected_lines)

    def test_based_on_prev_cpc_confirmed_only(self):
        """
        Has previous CPC upload; requesting confirmed annotations only.
        """
        # Upload CPC
        cpc_lines = [
            (r'"C:\CPCe codefiles\My codes.txt",'
             r'"C:\Panama dataset\1.jpg",6000,4500,20000,25000'),
            '285,4035',
            '5685,4035',
            '5685,435',
            '285,435',
            '3',
            self.img1_cpc_point_positions[0],
            self.img1_cpc_point_positions[1],
            self.img1_cpc_point_positions[2],
            '"1","","Notes","AC"',
            '"2","","Notes","BD"',
            '"3","A","Notes","EG"',
        ]
        cpc_lines.extend(['"Header value goes here"']*28)
        cpc_content = '\r\n'.join(cpc_lines) + '\r\n'
        f = ContentFile(cpc_content, name='Panama_1.cpc')
        self.upload_cpcs([f])

        # Add robot annotations: two confident, one non-confident.
        # This shouldn't change the expected lines whatsoever.
        self.add_robot_annotations(
            self.create_robot(self.source), self.img1,
            {1: ('B', 90), 2: ('B', 70), 3: ('B', 90)})
        expected_lines = cpc_lines[:]

        # Export, and get exported CPC content
        post_data = self.default_search_params.copy()
        post_data.update(
            # CPC prefs
            local_code_filepath=r'C:\CPCe codefiles\My codes.txt',
            local_image_dir=r'C:\Panama dataset',
            annotation_filter='confirmed_only',
        )
        response = self.export_cpcs(post_data)
        actual_cpc_content = self.export_response_to_cpc(
            response, 'Panama_1.cpc')

        self.assert_cpc_content_equal(actual_cpc_content, expected_lines)

    def test_based_on_prev_cpc_with_unconfirmed_confident(self):
        """
        Has previous CPC upload; including unconfirmed confident annotations.
        """
        # Upload CPC
        cpc_lines = [
            (r'"C:\CPCe codefiles\My codes.txt",'
             r'"C:\Panama dataset\1.jpg",6000,4500,20000,25000'),
            '285,4035',
            '5685,4035',
            '5685,435',
            '285,435',
            '3',
            self.img1_cpc_point_positions[0],
            self.img1_cpc_point_positions[1],
            self.img1_cpc_point_positions[2],
            '"1","","Notes","AC"',
            '"2","","Notes","BD"',
            '"3","A","Notes","EG"',
        ]
        cpc_lines.extend(['"Header value goes here"']*28)
        cpc_content = '\r\n'.join(cpc_lines) + '\r\n'
        f = ContentFile(cpc_content, name='Panama_1.cpc')
        self.upload_cpcs([f])

        # Add robot annotations: one confident, one non-confident,
        # one confident but not effective due to existing confirmed
        self.add_robot_annotations(
            self.create_robot(self.source), self.img1,
            {1: ('B', 90), 2: ('B', 70), 3: ('B', 90)})
        expected_lines = cpc_lines[:]
        # Only the confident + no existing confirmed one should be seen
        # in the export
        expected_lines[9] = '"1","B","Notes","AC"'

        # Export, and get exported CPC content
        post_data = self.default_search_params.copy()
        post_data.update(
            # CPC prefs
            local_code_filepath=r'C:\CPCe codefiles\My codes.txt',
            local_image_dir=r'C:\Panama dataset',
            annotation_filter='confirmed_and_confident',
        )
        response = self.export_cpcs(post_data)
        actual_cpc_content = self.export_response_to_cpc(
            response, 'Panama_1.cpc')

        self.assert_cpc_content_equal(actual_cpc_content, expected_lines)


class CPCUtilsTest(ClientTest):

    @classmethod
    def setUpTestData(cls):
        super(CPCUtilsTest, cls).setUpTestData()

        cls.user = cls.create_user()
        cls.source = cls.create_source(cls.user)
        labels = cls.create_labels(cls.user, ['A', 'B'], 'GroupA')
        cls.create_labelset(cls.user, cls.source, labels)
        cls.img1 = cls.upload_image(
            cls.user, cls.source,
            dict(filename='1.jpg', width=400, height=300))
        cls.img2 = cls.upload_image(cls.user, cls.source)

    def test_get_previous_cpcs_status(self):
        image_set = Image.objects.filter(source=self.source)
        self.assertEqual(get_previous_cpcs_status(image_set), 'none')

        self.img1.cpc_content = 'Some CPC file contents go here'
        self.img1.save()
        image_set = Image.objects.filter(source=self.source)
        self.assertEqual(get_previous_cpcs_status(image_set), 'some')

        self.img2.cpc_content = 'More CPC file contents go here'
        self.img2.save()
        image_set = Image.objects.filter(source=self.source)
        self.assertEqual(get_previous_cpcs_status(image_set), 'all')


class ZipTest(ClientTest):

    def test_write_zip(self):
        zip_stream = BytesIO()
        f1 = b'This is\r\na test file.'
        f2 = b'This is another test file.\r\n'
        names_and_streams = {
            'f1.txt': f1,
            'f2.txt': f2,
        }
        write_zip(zip_stream, names_and_streams)

        zip_file = ZipFile(zip_stream)
        zip_file.testzip()
        f1_read = zip_file.read('f1.txt')
        f2_read = zip_file.read('f2.txt')
        self.assertEqual(f1_read, b'This is\r\na test file.')
        self.assertEqual(f2_read, b'This is another test file.\r\n')
