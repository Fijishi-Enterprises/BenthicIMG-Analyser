from __future__ import unicode_literals
import os
import tempfile

from images.model_utils import PointGen
from lib.tests.utils import ManagementCommandTest


class RemovePointOutliersTest(ManagementCommandTest):

    def test_all_modes(self):
        # Set up data
        user = self.create_user()
        source = self.create_source(
            user, point_generation_type=PointGen.Types.SIMPLE,
            simple_number_of_points=5)
        labels = self.create_labels(user, ['A', 'B'], 'GroupA')
        self.create_labelset(user, source, labels)

        img1 = self.upload_image(
            user, source, image_options=dict(width=40, height=50))

        # 1 point has column out of range
        img2 = self.upload_image(
            user, source, image_options=dict(width=40, height=50))
        point = img2.point_set.all()[0]
        point.column = 47
        point.save()

        # 2 points have row out of range
        img3 = self.upload_image(
            user, source, image_options=dict(width=40, height=50))
        points = img3.point_set.all()
        point = points[2]
        point.row = 51
        point.save()
        point = points[4]
        point.row = 70
        point.save()

        with tempfile.NamedTemporaryFile(delete=False) as temporary_file:
            # The command opens the file from the pathname, so close it first.
            temporary_file.close()

            # Scan for outliers
            args = ['scan', temporary_file.name]
            self.call_command_and_get_output(
                'images', 'removepointoutliers', args=args)

            # Print outliers
            args = ['print', temporary_file.name]
            stdout_text, _ = self.call_command_and_get_output(
                'images', 'removepointoutliers', args=args)

            # Clean up outliers
            args = ['clean', temporary_file.name]
            self.call_command_and_get_output(
                'images', 'removepointoutliers', args=args)

            os.remove(temporary_file.name)

        # Verify output
        self.assertIn("{} 1".format(img2.pk), stdout_text)
        self.assertIn("{} 2".format(img3.pk), stdout_text)

        # Verify data changes: should have deleted 1 point from img2,
        # 2 points from img3
        img1.refresh_from_db()
        self.assertEqual(img1.point_set.all().count(), 5)
        img2.refresh_from_db()
        self.assertEqual(img2.point_set.all().count(), 4)
        img3.refresh_from_db()
        self.assertEqual(img3.point_set.all().count(), 3)
