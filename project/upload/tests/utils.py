from __future__ import unicode_literals
from abc import ABCMeta
from backports import csv
from io import StringIO
import six

from django.core.files.base import ContentFile
from django.urls import reverse

from lib.tests.utils import ClientTest


# Abstract class
@six.add_metaclass(ABCMeta)
class UploadAnnotationsTestMixin(object):

    @staticmethod
    def make_csv_file(csv_filename, rows):
        stream = StringIO()
        writer = csv.writer(stream)
        for row in rows:
            writer.writerow(row)

        f = ContentFile(stream.getvalue(), name=csv_filename)
        return f

    @staticmethod
    def make_cpc_file(
            cpc_filename, image_filepath, points,
            codes_filepath=r'C:\PROGRA~4\CPCE_4~1\SHALLO~1.TXT'):
        stream = StringIO()
        # Line 1
        line1_nums = '3000,1500,9000,4500'
        stream.writelines([
            '"{codes_filepath}","{image_filepath}",{line1_nums}\n'.format(
                codes_filepath=codes_filepath,
                image_filepath=image_filepath,
                line1_nums=line1_nums,
            )
        ])

        # Annotation area
        stream.writelines([
            '0,1500\n',
            '2000,1500\n',
            '2000,302.35\n',
            '0,302.35\n',
        ])

        # Number of points
        stream.writelines([
            '{num_points}\n'.format(num_points=len(points)),
        ])

        # Point positions
        stream.writelines(
            ['{x},{y}\n'.format(x=x, y=y) for x, y, _ in points]
        )

        # Label codes and notes
        label_code_lines = []
        for point_number, point in enumerate(points):
            _, _, label_code = point
            label_code_lines.append(
                '"{point_number}","{label_code}","Notes",""\n'.format(
                    point_number=point_number, label_code=label_code))
        stream.writelines(label_code_lines)

        # Metadata
        stream.writelines(['" "\n']*28)

        f = ContentFile(stream.getvalue(), name=cpc_filename)
        return f

    def preview_csv_annotations(self, user, source, csv_file):
        self.client.force_login(user)
        return self.client.post(
            reverse('upload_annotations_csv_preview_ajax', args=[source.pk]),
            {'csv_file': csv_file},
        )

    def preview_cpc_annotations(self, user, source, cpc_files):
        self.client.force_login(user)
        return self.client.post(
            reverse('upload_annotations_cpc_preview_ajax', args=[source.pk]),
            {'cpc_files': cpc_files},
        )

    def upload_annotations(self, user, source):
        self.client.force_login(user)
        return self.client.post(
            reverse('upload_annotations_ajax', args=[source.pk]),
        )


class UploadAnnotationsBaseTest(ClientTest, UploadAnnotationsTestMixin):
    pass
