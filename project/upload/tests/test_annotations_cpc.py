# -*- coding: utf-8 -*-
#
# Tests that only apply to CPC annotation uploads.

from __future__ import unicode_literals
from io import StringIO

from django.core.files.base import ContentFile
from django.urls import reverse

from .utils import UploadAnnotationsBaseTest


class CPCFormatTest(UploadAnnotationsBaseTest):
    """
    Tests (mostly error cases) specific to CPC format.
    """
    @classmethod
    def setUpTestData(cls):
        super(CPCFormatTest, cls).setUpTestData()

        cls.user = cls.create_user()
        cls.source = cls.create_source(cls.user)
        labels = cls.create_labels(cls.user, ['A', 'B'], 'Group1')
        cls.create_labelset(cls.user, cls.source, labels)

        cls.img1 = cls.upload_image(
            cls.user, cls.source,
            image_options=dict(filename='1.png', width=100, height=100))

    def test_one_line(self):
        stream = StringIO()
        # Line 1
        stream.writelines(['a,b,c,d,e,f\n'])
        cpc_file = ContentFile(stream.getvalue(), name='1.cpc')
        preview_response = self.preview_cpc_annotations(
            self.user, self.source, [cpc_file])

        self.assertDictEqual(
            preview_response.json(),
            dict(error="File 1.cpc seems to have too few lines."))

    def test_line_1_not_enough_tokens(self):
        stream = StringIO()
        # Line 1
        stream.writelines(['abc\n'])
        cpc_file = ContentFile(stream.getvalue(), name='1.cpc')
        preview_response = self.preview_cpc_annotations(
            self.user, self.source, [cpc_file])

        self.assertDictEqual(
            preview_response.json(),
            dict(error=(
                "File 1.cpc, line 1 has"
                " 1 comma-separated tokens, but"
                " 6 were expected.")))

    def test_line_1_too_many_tokens(self):
        stream = StringIO()
        # Line 1
        stream.writelines(['ab,cd,ef,gh,ij,kl,mn\n'])
        cpc_file = ContentFile(stream.getvalue(), name='1.cpc')
        preview_response = self.preview_cpc_annotations(
            self.user, self.source, [cpc_file])

        self.assertDictEqual(
            preview_response.json(),
            dict(error=(
                "File 1.cpc, line 1 has"
                " 7 comma-separated tokens, but"
                " 6 were expected.")))

    def test_line_1_quoted_commas_accepted(self):
        """Any commas between quotes should be considered part of a
        token, instead of a token separator."""
        stream = StringIO()
        # Line 1
        stream.writelines(['ab,cd,ef,"gh,ij",kl,mn\n'])
        cpc_file = ContentFile(stream.getvalue(), name='1.cpc')
        preview_response = self.preview_cpc_annotations(
            self.user, self.source, [cpc_file])

        # Should get past line 1 just fine, and then error due to not
        # having more lines.
        self.assertDictEqual(
            preview_response.json(),
            dict(error="File 1.cpc seems to have too few lines."))

    def test_line_2_wrong_number_of_tokens(self):
        stream = StringIO()
        # Line 1
        stream.writelines(['a,b,c,d,e,f\n'])
        # Line 2
        stream.writelines(['1,2,3\n'])
        cpc_file = ContentFile(stream.getvalue(), name='1.cpc')
        preview_response = self.preview_cpc_annotations(
            self.user, self.source, [cpc_file])

        self.assertDictEqual(
            preview_response.json(),
            dict(error=(
                "File 1.cpc, line 2 has"
                " 3 comma-separated tokens, but"
                " 2 were expected.")))

    def test_line_6_wrong_number_of_tokens(self):
        stream = StringIO()
        # Line 1
        stream.writelines(['a,b,c,d,e,f\n'])
        # Lines 2-5
        stream.writelines(['1,2\n']*4)
        # Line 6
        stream.writelines(['abc,def\n'])
        cpc_file = ContentFile(stream.getvalue(), name='1.cpc')
        preview_response = self.preview_cpc_annotations(
            self.user, self.source, [cpc_file])

        self.assertDictEqual(
            preview_response.json(),
            dict(error=(
                "File 1.cpc, line 6 has"
                " 2 comma-separated tokens, but"
                " 1 were expected.")))

    def test_line_6_not_number(self):
        stream = StringIO()
        # Line 1
        stream.writelines(['a,b,c,d,e,f\n'])
        # Lines 2-5
        stream.writelines(['1,2\n']*4)
        # Line 6
        stream.writelines(['abc\n'])
        cpc_file = ContentFile(stream.getvalue(), name='1.cpc')
        preview_response = self.preview_cpc_annotations(
            self.user, self.source, [cpc_file])

        self.assertDictEqual(
            preview_response.json(),
            dict(error=(
                "File 1.cpc, line 6 is supposed to have"
                " the number of points, but this line isn't a"
                " positive integer: abc")))

    def test_line_6_number_below_1(self):
        stream = StringIO()
        # Line 1
        stream.writelines(['a,b,c,d,e,f\n'])
        # Lines 2-5
        stream.writelines(['1,2\n']*4)
        # Line 6
        stream.writelines(['0\n'])
        cpc_file = ContentFile(stream.getvalue(), name='1.cpc')
        preview_response = self.preview_cpc_annotations(
            self.user, self.source, [cpc_file])

        self.assertDictEqual(
            preview_response.json(),
            dict(error=(
                "File 1.cpc, line 6 is supposed to have"
                " the number of points, but this line isn't a"
                " positive integer: 0")))

    def test_point_position_line_wrong_number_of_tokens(self):
        stream = StringIO()
        # Line 1
        stream.writelines(['a,b,c,d,e,f\n'])
        # Lines 2-5
        stream.writelines(['1,2\n']*4)
        # Line 6
        stream.writelines(['10\n'])
        # Line 7-15: point positions (one line too few)
        stream.writelines([
            '{n},{n}\n'.format(n=n*15) for n in range(9)])
        # Line 16: labels
        stream.writelines(['a,b,c,d\n'])
        cpc_file = ContentFile(stream.getvalue(), name='1.cpc')
        preview_response = self.preview_cpc_annotations(
            self.user, self.source, [cpc_file])

        self.assertDictEqual(
            preview_response.json(),
            dict(error=(
                "File 1.cpc, line 16 has"
                " 4 comma-separated tokens, but"
                " 2 were expected.")))

    def test_label_line_wrong_number_of_tokens(self):
        stream = StringIO()
        # Line 1
        stream.writelines(['a,b,c,d,e,f\n'])
        # Lines 2-5
        stream.writelines(['1,2\n']*4)
        # Line 6
        stream.writelines(['10\n'])
        # Lines 7-17: point positions (one line too many)
        stream.writelines([
            '{n},{n}\n'.format(n=n*15) for n in range(11)])
        cpc_file = ContentFile(stream.getvalue(), name='1.cpc')
        preview_response = self.preview_cpc_annotations(
            self.user, self.source, [cpc_file])

        self.assertDictEqual(
            preview_response.json(),
            dict(error=(
                "File 1.cpc, line 17 has"
                " 2 comma-separated tokens, but"
                " 4 were expected.")))

    def test_not_enough_label_lines(self):
        stream = StringIO()
        # Line 1
        stream.writelines(['a,b,c,d,e,f\n'])
        # Lines 2-5
        stream.writelines(['1,2\n']*4)
        # Line 6
        stream.writelines(['10\n'])
        # Lines 7-16: point positions
        stream.writelines([
            '{n},{n}\n'.format(n=n*15) for n in range(10)])
        # Line 17-25: labels (one line too few)
        stream.writelines(['a,b,c,d\n']*9)
        cpc_file = ContentFile(stream.getvalue(), name='1.cpc')
        preview_response = self.preview_cpc_annotations(
            self.user, self.source, [cpc_file])

        self.assertDictEqual(
            preview_response.json(),
            dict(error="File 1.cpc seems to have too few lines."))

    def test_multiple_cpcs_for_one_image(self):
        stream = StringIO()
        # Line 1
        stream.writelines(['a,"D:\\Panama transects\\1.png",c,d,e,f\n'])
        # Lines 2-5
        stream.writelines(['1,2\n']*4)
        # Line 6
        stream.writelines(['10\n'])
        # Lines 7-16: point positions
        # Multiply by 15 so they end up on different pixels. Otherwise
        # we may get the 'multiple points on same pixel' error instead.
        stream.writelines([
            '{n},{n}\n'.format(n=n*15) for n in range(10)])
        # Line 17-26: labels
        stream.writelines(['a,b,c,d\n']*10)
        cpc_file_1 = ContentFile(stream.getvalue(), name='1.cpc')

        stream = StringIO()
        # Line 1
        stream.writelines(['a,"D:\\GBR transects\\1.png",c,d,e,f\n'])
        # Lines 2-5
        stream.writelines(['1,2\n']*4)
        # Line 6
        stream.writelines(['10\n'])
        # Lines 7-16: point positions
        stream.writelines([
            '{n},{n}\n'.format(n=n*15) for n in range(10)])
        # Line 17-26: labels
        stream.writelines(['a,b,c,d\n']*10)
        cpc_file_2 = ContentFile(stream.getvalue(), name='2.cpc')

        preview_response = self.preview_cpc_annotations(
            self.user, self.source, [cpc_file_1, cpc_file_2])

        self.assertDictEqual(
            preview_response.json(),
            dict(error=(
                "Image 1.png has points from more than one .cpc file: 1.cpc"
                " and 2.cpc. There should be only one .cpc file"
                " per image.")))


class SaveCPCInfoTest(UploadAnnotationsBaseTest):
    """
    Tests for saving of CPC file info when uploading CPCs.
    """
    @classmethod
    def setUpTestData(cls):
        super(SaveCPCInfoTest, cls).setUpTestData()

        cls.user = cls.create_user()
        cls.source = cls.create_source(cls.user)
        labels = cls.create_labels(cls.user, ['A', 'B'], 'Group1')
        cls.create_labelset(cls.user, cls.source, labels)

        cls.img1 = cls.upload_image(
            cls.user, cls.source,
            image_options=dict(filename='1.jpg', width=100, height=100))
        cls.img2 = cls.upload_image(
            cls.user, cls.source,
            image_options=dict(filename='2.jpg', width=100, height=100))

    def test_cpc_content_one_image(self):
        cpc_files = [
            self.make_cpc_file(
                '1.cpc',
                r"C:\My Photos\2017-05-13 GBR\1.jpg", [
                    (49*15, 49*15, 'A'),
                    (59*15, 39*15, 'B')]),
        ]
        # Save the file content for comparison purposes.
        img1_expected_cpc_content = cpc_files[0].read()
        # Reset the file pointer so that the views can read from the start.
        cpc_files[0].seek(0)

        self.preview_cpc_annotations(self.user, self.source, cpc_files)
        self.upload_annotations(self.user, self.source)

        self.img1.refresh_from_db()
        self.assertEqual(self.img1.cpc_content, img1_expected_cpc_content)
        self.assertEqual(self.img1.cpc_filename, '1.cpc')
        self.img2.refresh_from_db()
        self.assertEqual(self.img2.cpc_content, '')
        self.assertEqual(self.img2.cpc_filename, '')

    def test_cpc_content_multiple_images(self):
        cpc_files = [
            self.make_cpc_file(
                'GBR_1.cpc',
                r"C:\My Photos\2017-05-13 GBR\1.jpg", [
                    (49*15, 49*15, 'A'),
                    (59*15, 39*15, 'B')]),
            self.make_cpc_file(
                'GBR_2.cpc',
                r"C:\My Photos\2017-05-13 GBR\2.jpg", [
                    (69*15, 29*15, 'A'),
                    (79*15, 19*15, 'A')]),
        ]
        # Save the file content for comparison purposes.
        img1_expected_cpc_content = cpc_files[0].read()
        img2_expected_cpc_content = cpc_files[1].read()
        # Reset the file pointer so that the views can read from the start.
        cpc_files[0].seek(0)
        cpc_files[1].seek(0)

        self.preview_cpc_annotations(self.user, self.source, cpc_files)
        self.upload_annotations(self.user, self.source)

        self.img1.refresh_from_db()
        self.assertEqual(self.img1.cpc_content, img1_expected_cpc_content)
        self.assertEqual(self.img1.cpc_filename, 'GBR_1.cpc')
        self.img2.refresh_from_db()
        self.assertEqual(self.img2.cpc_content, img2_expected_cpc_content)
        self.assertEqual(self.img2.cpc_filename, 'GBR_2.cpc')

    def test_source_fields(self):
        cpc_files = [
            self.make_cpc_file(
                '1.cpc',
                r"C:\My Photos\2017-05-13 GBR\1.jpg", [
                    (49*15, 49*15, 'A'),
                    (59*15, 39*15, 'B')],
                codes_filepath=r'C:\PROGRA~4\CPCE_4~1\SHALLO~1.TXT'),
            self.make_cpc_file(
                '2.cpc',
                r"C:\My Photos\2017-05-13 GBR\2.jpg", [
                    (69*15, 29*15, 'A'),
                    (79*15, 19*15, 'A')],
                codes_filepath=r'C:\My Photos\CPCe codefiles\GBR codes.txt'),
        ]
        self.preview_cpc_annotations(self.user, self.source, cpc_files)
        self.upload_annotations(self.user, self.source)

        self.source.refresh_from_db()
        # Although it's an implementation detail and not part of spec,
        # the last uploaded CPC should have its values used in a multi-CPC
        # upload.
        self.assertEqual(
            self.source.cpce_code_filepath,
            r'C:\My Photos\CPCe codefiles\GBR codes.txt')
        self.assertEqual(
            self.source.cpce_image_dir, r'C:\My Photos\2017-05-13 GBR')


class CPCImageMatchingTest(UploadAnnotationsBaseTest):
    """
    Tests for matching uploaded CPCs to images in the source.
    """
    @classmethod
    def setUpTestData(cls):
        super(CPCImageMatchingTest, cls).setUpTestData()

        cls.user = cls.create_user()
        cls.source = cls.create_source(cls.user)
        labels = cls.create_labels(cls.user, ['A', 'B'], 'Group1')
        cls.create_labelset(cls.user, cls.source, labels)

    def upload_image_with_name(self, image_name):
        img = self.upload_image(self.user, self.source)
        img.metadata.name = image_name
        img.metadata.save()
        return img

    def upload_preview_for_image_name(self, image_name):
        cpc_files = [
            self.make_cpc_file(
                '1.cpc',
                image_name,
                [(9*15, 9*15, 'A')],
                codes_filepath=r'C:\PROGRA~4\CPCE_4~1\SHALLO~1.TXT'),
        ]
        return self.preview_cpc_annotations(self.user, self.source, cpc_files)

    def assertImageInPreview(self, img, preview_response):
        self.assertDictEqual(
            preview_response.json()['previewTable'][0],
            dict(
                name=img.metadata.name,
                link=reverse('annotation_tool', args=[img.pk]),
                createInfo="Will create 1 points, 1 annotations"))

    def test_favor_longer_path_suffix_matches(self):
        # Scramble the upload order, to ensure the matching logic doesn't
        # depend on order.
        img1 = self.upload_image_with_name(r'D:\Site A\Transect 1\01.jpg')
        img4 = self.upload_image_with_name(r'01.jpg')
        img2 = self.upload_image_with_name(r'Site A\Transect 1\01.jpg')
        img3 = self.upload_image_with_name(r'Transect 1\01.jpg')

        preview_response = self.upload_preview_for_image_name(
            r'D:\Site A\Transect 1\01.jpg')
        self.assertImageInPreview(img1, preview_response)

        preview_response = self.upload_preview_for_image_name(
            r'C:\Site A\Transect 1\01.jpg')
        self.assertImageInPreview(img2, preview_response)

        preview_response = self.upload_preview_for_image_name(
            r'D:\Site B\Transect 1\01.jpg')
        self.assertImageInPreview(img3, preview_response)

        preview_response = self.upload_preview_for_image_name(
            r'D:\Site A\Transect 8\01.jpg')
        self.assertImageInPreview(img4, preview_response)

    def test_do_not_partial_match_filenames(self):
        self.upload_image_with_name(r'IMG_0001.JPG')

        # 'Superstring'
        preview_response = self.upload_preview_for_image_name(
            r'D:\Site A\Transect 1\Quadrant_5_IMG_0001.JPG')
        self.assertDictEqual(
            preview_response.json(),
            dict(error="No matching image names found in the source"))

        # Substring
        preview_response = self.upload_preview_for_image_name(
            r'0001.JPG')
        self.assertDictEqual(
            preview_response.json(),
            dict(error="No matching image names found in the source"))

    def test_slash_direction_does_not_matter(self):
        self.upload_image_with_name(r'01.jpg')

        # Forward in image name, back in CPC
        transect_img = self.upload_image_with_name(r'Transect 1/01.jpg')
        preview_response = self.upload_preview_for_image_name(
            r'D:\Site A\Transect 1\01.jpg')
        self.assertImageInPreview(transect_img, preview_response)

        # Back in image name, forward in CPC
        quadrat_img = self.upload_image_with_name(r'Quadrat 3\01.jpg')
        preview_response = self.upload_preview_for_image_name(
            r'D:/Site A/Quadrat 3/01.jpg')
        self.assertImageInPreview(quadrat_img, preview_response)
