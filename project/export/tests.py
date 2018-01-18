from __future__ import unicode_literals
from zipfile import ZipFile
from six import BytesIO, StringIO

from django.core.files.base import ContentFile
from django.core.urlresolvers import reverse

from .utils import (
    write_annotations_cpc, write_annotations_cpc_based_on_prev_cpc,
    get_previous_cpcs_status, write_zip)
from images.model_utils import PointGen
from images.models import Image
from lib.test_utils import ClientTest


class CPCUtilsTest(ClientTest):

    @classmethod
    def setUpTestData(cls):
        super(CPCUtilsTest, cls).setUpTestData()

        cls.user = cls.create_user()

        cls.source = cls.create_source(
            cls.user,
            point_generation_type=PointGen.Types.UNIFORM,
            number_of_cell_rows=2, number_of_cell_columns=3,
            min_x=5, max_x=95, min_y=10, max_y=90,
        )
        labels = cls.create_labels(cls.user, ['A', 'B'], 'GroupA')
        cls.create_labelset(cls.user, cls.source, labels)
        cls.img1 = cls.upload_image(
            cls.user, cls.source,
            dict(filename='1.jpg', width=400, height=300))
        cls.img2 = cls.upload_image(cls.user, cls.source)
        annotations = {1: 'A', 2: 'B', 3: 'A', 4: 'A'}
        cls.add_annotations(cls.user, cls.img1, annotations)

    def test_write_annotations_cpc_from_scratch(self):

        cpc_prefs = dict(
            local_code_filepath=r'C:\CPCe codefiles\My codes.txt',
            local_image_dir=r'C:\Panama dataset',
        )

        cpc_stream = StringIO()
        write_annotations_cpc(cpc_stream, self.img1, cpc_prefs)

        expected_lines = [
            r'"C:\CPCe codefiles\My codes.txt","C:\Panama dataset\1.jpg",6000,4500,14400,10800',
            '285,4035',
            '5685,4035',
            '5685,435',
            '285,435',
            '6',
            '1170,1320',
            '2970,1320',
            '4785,1320',
            '1170,3135',
            '2970,3135',
            '4785,3135',
            '"1","A","Notes",""',
            '"2","B","Notes",""',
            '"3","A","Notes",""',
            '"4","A","Notes",""',
            '"5","","Notes",""',
            '"6","","Notes",""',
        ]
        expected_lines.extend(['" "']*28)
        # Yes, CPCe does put a newline at the end
        expected_cpc_content = '\r\n'.join(expected_lines) + '\r\n'

        actual_cpc_content = cpc_stream.getvalue()
        actual_lines = actual_cpc_content.splitlines()
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

    def test_write_annotations_cpc_based_on_prev_cpc(self):

        cpc_lines = [
            r'"C:\CPCe codefiles\My codes.txt","C:\Panama dataset\1.jpg",6000,4500,20000,25000',
            '285,4035',
            '5685,4035',
            '5685,435',
            '285,435',
            '2',
            '1170,1320',
            '2970,1320',
            # Add notes codes
            '"1","A","Notes","AC"',
            '"2","","Notes","BD"',
        ]
        # Add some header values
        cpc_lines.extend(['"Header value goes here"']*28)
        # Yes, CPCe does put a newline at the end
        cpc_content = '\r\n'.join(cpc_lines) + '\r\n'

        # Upload
        self.client.force_login(self.user)
        f = ContentFile(cpc_content, name='Panama_1.cpc')
        self.client.post(
            reverse('upload_annotations_cpc_preview_ajax', args=[
                self.source.pk]),
            {'cpc_files': [f]},
        )
        self.client.post(
            reverse('upload_annotations_ajax', args=[self.source.pk]),
        )
        #import pdb; pdb.set_trace()
        # Change some annotations
        annotations = {1: 'B', 2: 'A'}
        self.add_annotations(self.user, self.img1, annotations)
        post_export_expected_lines = cpc_lines[:]
        post_export_expected_lines[8] = '"1","B","Notes","AC"'
        post_export_expected_lines[9] = '"2","A","Notes","BD"'
        post_export_expected_cpc_content = \
            '\r\n'.join(post_export_expected_lines) + '\r\n'

        cpc_stream = StringIO()
        self.img1.refresh_from_db()
        write_annotations_cpc_based_on_prev_cpc(cpc_stream, self.img1)

        actual_cpc_content = cpc_stream.getvalue()
        actual_lines = actual_cpc_content.splitlines()
        # Compare individual lines (so that if we get a mismatch, the error
        # message will be readable)
        for line_num, actual_line in enumerate(actual_lines, 1):
            expected_line = post_export_expected_lines[line_num-1]
            self.assertEqual(actual_line, expected_line, msg=(
                "Line {line_num} not equal | Actual: {actual_line}"
                " | Expected: {expected_line}").format(
                line_num=line_num, actual_line=actual_line,
                expected_line=expected_line,
            ))
        # Compare entire file (to ensure line separator types are correct too)
        self.assertEqual(actual_cpc_content, post_export_expected_cpc_content)

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
