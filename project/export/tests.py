from __future__ import unicode_literals
from io import BytesIO
from zipfile import ZipFile

from .utils import write_annotations_cpc, write_zip
from images.model_utils import PointGen
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
            dict(filename='1.png', width=400, height=300))
        annotations = {1: 'A', 2: 'B', 3: 'A', 4: 'A'}
        cls.add_annotations(cls.user, cls.img1, annotations)

    def test_write_annotations_cpc(self):

        cpc_prefs = dict(
            local_code_filepath=r'C:\CPCe codefiles\My codes.txt',
            local_image_dir=r'C:\Panama dataset',
        )

        cpc_stream = BytesIO()
        write_annotations_cpc(cpc_stream, self.img1, cpc_prefs)

        expected_lines = [
            r'"C:\CPCe codefiles\My codes.txt","C:\Panama dataset\1.png",6000,4500,14400,10800',
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
        # Compare individual lines (for readable error messages)
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
