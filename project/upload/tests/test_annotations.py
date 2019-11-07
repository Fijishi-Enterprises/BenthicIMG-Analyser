# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import codecs
from io import StringIO

from django.core.files.base import ContentFile
from django.urls import reverse

from accounts.utils import get_imported_user
from annotations.model_utils import AnnotationAreaUtils
from annotations.models import Annotation
from images.model_utils import PointGen
from images.models import Point
from lib.tests.utils import ClientTest, sample_image_as_file
from upload.tests.utils import UploadAnnotationsTestMixin


class UploadAnnotationsNoLabelsetTest(ClientTest):
    """
    Point/annotation upload attempts with no labelset.
    This should just fail to reach the page.
    """
    @classmethod
    def setUpTestData(cls):
        super(UploadAnnotationsNoLabelsetTest, cls).setUpTestData()

        cls.user = cls.create_user()
        cls.source = cls.create_source(cls.user)

    def test_page_csv(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse('upload_annotations_csv', args=[self.source.pk]),
        )
        self.assertContains(
            response,
            "You must create a labelset before uploading annotations.")
        self.assertTemplateUsed(response, 'labels/labelset_required.html')

    def test_preview_csv(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse('upload_annotations_csv_preview_ajax', args=[
                self.source.pk]),
        )
        self.assertContains(
            response,
            "You must create a labelset before uploading annotations.")
        self.assertTemplateUsed(response, 'labels/labelset_required.html')

    def test_page_cpc(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse('upload_annotations_cpc', args=[self.source.pk]),
        )
        self.assertContains(
            response,
            "You must create a labelset before uploading annotations.")
        self.assertTemplateUsed(response, 'labels/labelset_required.html')

    def test_preview_cpc(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse('upload_annotations_cpc_preview_ajax', args=[
                self.source.pk]),
        )
        self.assertContains(
            response,
            "You must create a labelset before uploading annotations.")
        self.assertTemplateUsed(response, 'labels/labelset_required.html')

    def test_upload(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse('upload_annotations_ajax', args=[self.source.pk]),
        )
        self.assertContains(
            response,
            "You must create a labelset before uploading annotations.")
        self.assertTemplateUsed(response, 'labels/labelset_required.html')


class UploadAnnotationsBaseTest(ClientTest, UploadAnnotationsTestMixin):
    pass


class UploadAnnotationsTest(UploadAnnotationsBaseTest):
    """
    Point/annotation upload and preview.
    """
    @classmethod
    def setUpTestData(cls):
        super(UploadAnnotationsTest, cls).setUpTestData()

        cls.user = cls.create_user()
        cls.source = cls.create_source(cls.user)
        labels = cls.create_labels(cls.user, ['A', 'B'], 'Group1')
        cls.create_labelset(cls.user, cls.source, labels)
        cls.img1 = cls.upload_image(
            cls.user, cls.source,
            image_options=dict(filename='1.png', width=200, height=100))
        cls.img2 = cls.upload_image(
            cls.user, cls.source,
            image_options=dict(filename='2.png', width=200, height=100))
        cls.img3 = cls.upload_image(
            cls.user, cls.source,
            image_options=dict(filename='3.png', width=200, height=100))

        # Get full diff output if something like an assertEqual fails
        cls.maxDiff = None

    def test_points_only_csv(self):
        """
        No annotations on specified points.
        """
        rows = [
            ['Name', 'Column', 'Row'],
            ['1.png', 50, 50],
            ['1.png', 60, 40],
            ['1.png', 70, 30],
            ['1.png', 80, 20],
            ['1.png', 90, 10],
            ['2.png', 1, 1],
            ['2.png', 200, 100],
            ['2.png', 44, 44],
        ]
        csv_file = self.make_csv_file('A.csv', rows)
        preview_response = self.preview_csv_annotations(
            self.user, self.source, csv_file)
        upload_response = self.upload_annotations(self.user, self.source)

        self.check_points_only(preview_response, upload_response)

    def test_points_only_cpc(self):
        """
        No annotations on specified points.
        """
        cpc_files = [
            self.make_cpc_file(
                '1.cpc',
                r"C:\My Photos\2017-05-13 GBR\1.png", [
                    (49*15, 49*15, ''),
                    (59*15, 39*15, ''),
                    (69*15, 29*15, ''),
                    (79*15, 19*15, ''),
                    (89*15, 9*15, '')]),
            self.make_cpc_file(
                '2.cpc',
                r"C:\My Photos\2017-05-13 GBR\2.png", [
                    (0, 0, ''),
                    (2992, 1492, ''),
                    (43*15, 43*15, '')]),
        ]
        preview_response = self.preview_cpc_annotations(
            self.user, self.source, cpc_files)
        upload_response = self.upload_annotations(self.user, self.source)

        self.check_points_only(preview_response, upload_response)

    def check_points_only(self, preview_response, upload_response):

        self.assertDictEqual(
            preview_response.json(),
            dict(
                success=True,
                previewTable=[
                    dict(
                        name=self.img1.metadata.name,
                        link=reverse(
                            'annotation_tool',
                            kwargs=dict(image_id=self.img1.pk)),
                        createInfo="Will create 5 points, 0 annotations",
                    ),
                    dict(
                        name=self.img2.metadata.name,
                        link=reverse(
                            'annotation_tool',
                            kwargs=dict(image_id=self.img2.pk)),
                        createInfo="Will create 3 points, 0 annotations",
                    ),
                ],
                previewDetails=dict(
                    numImages=2,
                    totalPoints=8,
                    totalAnnotations=0,
                    numImagesWithExistingAnnotations=0,
                ),
            ),
        )

        self.assertDictEqual(upload_response.json(), dict(success=True))

        values_set = set(
            Point.objects.filter(image__in=[self.img1, self.img2])
            .values_list('column', 'row', 'point_number', 'image_id'))
        self.assertSetEqual(values_set, {
            (50, 50, 1, self.img1.pk),
            (60, 40, 2, self.img1.pk),
            (70, 30, 3, self.img1.pk),
            (80, 20, 4, self.img1.pk),
            (90, 10, 5, self.img1.pk),
            (1,  1,  1, self.img2.pk),
            (200, 100, 2, self.img2.pk),
            (44, 44, 3, self.img2.pk),
        })

        self.img1.refresh_from_db()
        self.assertEqual(
            self.img1.point_generation_method,
            PointGen.args_to_db_format(
                point_generation_type=PointGen.Types.IMPORTED,
                imported_number_of_points=5))
        self.assertEqual(
            self.img1.metadata.annotation_area,
            AnnotationAreaUtils.IMPORTED_STR)

        self.img2.refresh_from_db()
        self.assertEqual(
            self.img2.point_generation_method,
            PointGen.args_to_db_format(
                point_generation_type=PointGen.Types.IMPORTED,
                imported_number_of_points=3))
        self.assertEqual(
            self.img2.metadata.annotation_area,
            AnnotationAreaUtils.IMPORTED_STR)

    def test_all_annotations_csv(self):
        """
        Annotations on all specified points.
        """
        rows = [
            ['Name', 'Column', 'Row', 'Label'],
            ['1.png', 50, 50, 'A'],
            ['1.png', 60, 40, 'B'],
            ['2.png', 70, 30, 'A'],
            ['2.png', 80, 20, 'A'],
        ]
        csv_file = self.make_csv_file('A.csv', rows)
        preview_response = self.preview_csv_annotations(
            self.user, self.source, csv_file)
        upload_response = self.upload_annotations(self.user, self.source)

        self.check_all_annotations(preview_response, upload_response)

    def test_all_annotations_cpc(self):
        """
        Annotations on all specified points.
        """
        cpc_files = [
            self.make_cpc_file(
                '1.cpc',
                r"C:\My Photos\2017-05-13 GBR\1.png", [
                    (49*15, 49*15, 'A'),
                    (59*15, 39*15, 'B')]),
            self.make_cpc_file(
                '2.cpc',
                r"C:\My Photos\2017-05-13 GBR\2.png", [
                    (69*15, 29*15, 'A'),
                    (79*15, 19*15, 'A')]),
        ]
        preview_response = self.preview_cpc_annotations(
            self.user, self.source, cpc_files)
        upload_response = self.upload_annotations(self.user, self.source)

        self.check_all_annotations(preview_response, upload_response)

    def check_all_annotations(self, preview_response, upload_response):

        self.assertDictEqual(
            preview_response.json(),
            dict(
                success=True,
                previewTable=[
                    dict(
                        name=self.img1.metadata.name,
                        link=reverse(
                            'annotation_tool',
                            kwargs=dict(image_id=self.img1.pk)),
                        createInfo="Will create 2 points, 2 annotations",
                    ),
                    dict(
                        name=self.img2.metadata.name,
                        link=reverse(
                            'annotation_tool',
                            kwargs=dict(image_id=self.img2.pk)),
                        createInfo="Will create 2 points, 2 annotations",
                    ),
                ],
                previewDetails=dict(
                    numImages=2,
                    totalPoints=4,
                    totalAnnotations=4,
                    numImagesWithExistingAnnotations=0,
                ),
            ),
        )

        self.assertDictEqual(upload_response.json(), dict(success=True))

        values_set = set(
            Point.objects.filter(image__in=[self.img1, self.img2])
            .values_list('column', 'row', 'point_number', 'image_id'))
        self.assertSetEqual(values_set, {
            (50, 50, 1, self.img1.pk),
            (60, 40, 2, self.img1.pk),
            (70, 30, 1, self.img2.pk),
            (80, 20, 2, self.img2.pk),
        })

        annotations = Annotation.objects.filter(
            image__in=[self.img1, self.img2])
        values_set = set(
            (a.label_code, a.point.pk, a.image.pk)
            for a in annotations
        )
        self.assertSetEqual(values_set, {
            ('A', Point.objects.get(
                point_number=1, image=self.img1).pk, self.img1.pk),
            ('B', Point.objects.get(
                point_number=2, image=self.img1).pk, self.img1.pk),
            ('A', Point.objects.get(
                point_number=1, image=self.img2).pk, self.img2.pk),
            ('A', Point.objects.get(
                point_number=2, image=self.img2).pk, self.img2.pk),
        })
        for annotation in annotations:
            self.assertEqual(annotation.source.pk, self.source.pk)
            self.assertEqual(annotation.user.pk, get_imported_user().pk)
            self.assertEqual(annotation.robot_version, None)
            self.assertLess(
                self.source.create_date, annotation.annotation_date)

    def test_some_annotations_csv(self):
        """
        Annotations on some specified points, but not all.
        """
        rows = [
            ['Name', 'Column', 'Row', 'Label'],
            ['1.png', 50, 50, 'A'],
            ['1.png', 60, 40, 'B'],
            ['2.png', 70, 30, 'A'],
            ['2.png', 80, 20],
            ['3.png', 70, 30],
            ['3.png', 80, 20],
        ]
        csv_file = self.make_csv_file('A.csv', rows)
        preview_response = self.preview_csv_annotations(
            self.user, self.source, csv_file)
        upload_response = self.upload_annotations(self.user, self.source)

        self.check_some_annotations(preview_response, upload_response)

    def test_some_annotations_cpc(self):
        """
        Annotations on some specified points, but not all.
        """
        cpc_files = [
            self.make_cpc_file(
                '1.cpc',
                r"C:\My Photos\2017-05-13 GBR\1.png", [
                    (49*15, 49*15, 'A'),
                    (59*15, 39*15, 'B')]),
            self.make_cpc_file(
                '2.cpc',
                r"C:\My Photos\2017-05-13 GBR\2.png", [
                    (69*15, 29*15, 'A'),
                    (79*15, 19*15, '')]),
            self.make_cpc_file(
                '3.cpc',
                r"C:\My Photos\2017-05-13 GBR\3.png", [
                    (69*15, 29*15, ''),
                    (79*15, 19*15, '')]),
        ]
        preview_response = self.preview_cpc_annotations(
            self.user, self.source, cpc_files)
        upload_response = self.upload_annotations(self.user, self.source)

        self.check_some_annotations(preview_response, upload_response)

    def check_some_annotations(self, preview_response, upload_response):

        self.assertDictEqual(
            preview_response.json(),
            dict(
                success=True,
                previewTable=[
                    dict(
                        name=self.img1.metadata.name,
                        link=reverse(
                            'annotation_tool',
                            kwargs=dict(image_id=self.img1.pk)),
                        createInfo="Will create 2 points, 2 annotations",
                    ),
                    dict(
                        name=self.img2.metadata.name,
                        link=reverse(
                            'annotation_tool',
                            kwargs=dict(image_id=self.img2.pk)),
                        createInfo="Will create 2 points, 1 annotations",
                    ),
                    dict(
                        name=self.img3.metadata.name,
                        link=reverse(
                            'annotation_tool',
                            kwargs=dict(image_id=self.img3.pk)),
                        createInfo="Will create 2 points, 0 annotations",
                    ),
                ],
                previewDetails=dict(
                    numImages=3,
                    totalPoints=6,
                    totalAnnotations=3,
                    numImagesWithExistingAnnotations=0,
                ),
            ),
        )

        self.assertDictEqual(upload_response.json(), dict(success=True))

        values_set = set(
            Point.objects.filter(
                image__in=[self.img1, self.img2, self.img3])
            .values_list('column', 'row', 'point_number', 'image_id'))
        self.assertSetEqual(values_set, {
            (50, 50, 1, self.img1.pk),
            (60, 40, 2, self.img1.pk),
            (70, 30, 1, self.img2.pk),
            (80, 20, 2, self.img2.pk),
            (70, 30, 1, self.img3.pk),
            (80, 20, 2, self.img3.pk),
        })

        annotations = Annotation.objects.filter(
            image__in=[self.img1, self.img2, self.img3])
        values_set = set(
            (a.label_code, a.point.pk, a.image.pk)
            for a in annotations
        )
        self.assertSetEqual(values_set, {
            ('A', Point.objects.get(
                point_number=1, image=self.img1).pk, self.img1.pk),
            ('B', Point.objects.get(
                point_number=2, image=self.img1).pk, self.img1.pk),
            ('A', Point.objects.get(
                point_number=1, image=self.img2).pk, self.img2.pk),
        })
        for annotation in annotations:
            self.assertEqual(annotation.source.pk, self.source.pk)
            self.assertEqual(annotation.user.pk, get_imported_user().pk)
            self.assertEqual(annotation.robot_version, None)
            self.assertLess(
                self.source.create_date, annotation.annotation_date)

    def test_overwrite_annotations_csv(self):
        """
        Save some annotations, then overwrite those with other annotations.
        """
        rows = [
            ['Name', 'Column', 'Row', 'Label'],
            ['1.png', 50, 50, 'A'],
            ['1.png', 60, 40, 'B'],
            ['2.png', 70, 30, 'A'],
            ['2.png', 80, 20],
            ['3.png', 70, 30],
            ['3.png', 80, 20],
        ]
        csv_file = self.make_csv_file('A.csv', rows)
        self.preview_csv_annotations(self.user, self.source, csv_file)
        self.upload_annotations(self.user, self.source)

        rows = [
            ['Name', 'Column', 'Row', 'Label'],
            ['1.png', 10, 10, 'A'],
            ['1.png', 20, 20, 'A'],
            ['2.png', 30, 30],
            ['2.png', 40, 40],
            ['3.png', 50, 50, 'A'],
            ['3.png', 60, 60, 'B'],
        ]
        csv_file = self.make_csv_file('B.csv', rows)
        preview_response = self.preview_csv_annotations(
            self.user, self.source, csv_file)
        upload_response = self.upload_annotations(self.user, self.source)

        self.check_overwrite_annotations(preview_response, upload_response)

    def test_overwrite_annotations_cpc(self):
        """
        Save some annotations, then overwrite those with other annotations.
        """
        cpc_files = [
            self.make_cpc_file(
                '1.cpc',
                r"C:\My Photos\2017-05-13 GBR\1.png", [
                    (49*15, 49*15, 'A'),
                    (59*15, 39*15, 'B')]),
            self.make_cpc_file(
                '2.cpc',
                r"C:\My Photos\2017-05-13 GBR\2.png", [
                    (69*15, 29*15, 'A'),
                    (79*15, 19*15, '')]),
            self.make_cpc_file(
                '3.cpc',
                r"C:\My Photos\2017-05-13 GBR\3.png", [
                    (69*15, 29*15, ''),
                    (79*15, 19*15, '')]),
        ]
        self.preview_cpc_annotations(self.user, self.source, cpc_files)
        self.upload_annotations(self.user, self.source)

        cpc_files = [
            self.make_cpc_file(
                '1.cpc',
                r"C:\My Photos\2017-05-13 GBR\1.png", [
                    (9*15, 9*15, 'A'),
                    (19*15, 19*15, 'A')]),
            self.make_cpc_file(
                '2.cpc',
                r"C:\My Photos\2017-05-13 GBR\2.png", [
                    (29*15, 29*15, ''),
                    (39*15, 39*15, '')]),
            self.make_cpc_file(
                '3.cpc',
                r"C:\My Photos\2017-05-13 GBR\3.png", [
                    (49*15, 49*15, 'A'),
                    (59*15, 59*15, 'B')]),
        ]
        preview_response = self.preview_cpc_annotations(
            self.user, self.source, cpc_files)
        upload_response = self.upload_annotations(self.user, self.source)

        self.check_overwrite_annotations(preview_response, upload_response)

    def check_overwrite_annotations(self, preview_response, upload_response):

        self.assertDictEqual(
            preview_response.json(),
            dict(
                success=True,
                previewTable=[
                    dict(
                        name=self.img1.metadata.name,
                        link=reverse(
                            'annotation_tool',
                            kwargs=dict(image_id=self.img1.pk)),
                        createInfo="Will create 2 points, 2 annotations",
                        deleteInfo="Will delete 2 existing annotations",
                    ),
                    dict(
                        name=self.img2.metadata.name,
                        link=reverse(
                            'annotation_tool',
                            kwargs=dict(image_id=self.img2.pk)),
                        createInfo="Will create 2 points, 0 annotations",
                        deleteInfo="Will delete 1 existing annotations",
                    ),
                    dict(
                        name=self.img3.metadata.name,
                        link=reverse(
                            'annotation_tool',
                            kwargs=dict(image_id=self.img3.pk)),
                        createInfo="Will create 2 points, 2 annotations",
                    ),
                ],
                previewDetails=dict(
                    numImages=3,
                    totalPoints=6,
                    totalAnnotations=4,
                    numImagesWithExistingAnnotations=2,
                ),
            ),
        )

        self.assertDictEqual(upload_response.json(), dict(success=True))

        values_set = set(
            Point.objects.filter(
                image__in=[self.img1, self.img2, self.img3])
            .values_list('column', 'row', 'point_number', 'image_id'))
        self.assertSetEqual(values_set, {
            (10, 10, 1, self.img1.pk),
            (20, 20, 2, self.img1.pk),
            (30, 30, 1, self.img2.pk),
            (40, 40, 2, self.img2.pk),
            (50, 50, 1, self.img3.pk),
            (60, 60, 2, self.img3.pk),
        })

        annotations = Annotation.objects.filter(
            image__in=[self.img1, self.img2, self.img3])
        values_set = set(
            (a.label_code, a.point.pk, a.image.pk)
            for a in annotations
        )
        self.assertSetEqual(values_set, {
            ('A', Point.objects.get(
                point_number=1, image=self.img1).pk, self.img1.pk),
            ('A', Point.objects.get(
                point_number=2, image=self.img1).pk, self.img1.pk),
            ('A', Point.objects.get(
                point_number=1, image=self.img3).pk, self.img3.pk),
            ('B', Point.objects.get(
                point_number=2, image=self.img3).pk, self.img3.pk),
        })

    def test_label_codes_different_case_csv(self):
        """
        The import file's label codes can use different upper/lower case
        and still be matched to the corresponding labelset label codes.
        """
        # Make a longer-than-1-char label code so we can test that
        # lower() is being used on both the label's code and the CSV value
        labels = self.create_labels(self.user, ['Abc'], 'Group1')
        self.create_labelset(self.user, self.source, labels)

        rows = [
            ['Name', 'Column', 'Row', 'Label'],
            ['1.png', 60, 40, 'aBc'],
        ]
        csv_file = self.make_csv_file('A.csv', rows)
        preview_response = self.preview_csv_annotations(
            self.user, self.source, csv_file)
        upload_response = self.upload_annotations(self.user, self.source)

        self.check_label_codes_different_case(
            preview_response, upload_response)

    def test_label_codes_different_case_cpc(self):
        """
        The import file's label codes can use different upper/lower case
        and still be matched to the corresponding labelset label codes.
        """
        # Make a longer-than-1-char label code so we can test that
        # lower() is being used on both the label's code and the CSV value
        labels = self.create_labels(self.user, ['Abc'], 'Group1')
        self.create_labelset(self.user, self.source, labels)

        cpc_files = [
            self.make_cpc_file(
                '1.cpc',
                r"C:\My Photos\2017-05-13 GBR\1.png", [
                    (59*15, 39*15, 'aBc')]),
        ]
        preview_response = self.preview_cpc_annotations(
            self.user, self.source, cpc_files)
        upload_response = self.upload_annotations(self.user, self.source)

        self.check_label_codes_different_case(
            preview_response, upload_response)

    def check_label_codes_different_case(
            self, preview_response, upload_response):

        self.assertDictEqual(
            preview_response.json(),
            dict(
                success=True,
                previewTable=[
                    dict(
                        name=self.img1.metadata.name,
                        link=reverse(
                            'annotation_tool',
                            kwargs=dict(image_id=self.img1.pk)),
                        createInfo="Will create 1 points, 1 annotations",
                    ),
                ],
                previewDetails=dict(
                    numImages=1,
                    totalPoints=1,
                    totalAnnotations=1,
                    numImagesWithExistingAnnotations=0,
                ),
            ),
        )

        self.assertDictEqual(upload_response.json(), dict(success=True))

        values_set = set(
            Point.objects.filter(image__in=[self.img1])
            .values_list('column', 'row', 'point_number', 'image_id'))
        self.assertSetEqual(values_set, {
            (60, 40, 1, self.img1.pk),
        })

        annotations = Annotation.objects.filter(image__in=[self.img1])
        values_set = set(
            (a.label_code, a.point.pk, a.image.pk)
            for a in annotations
        )
        self.assertSetEqual(values_set, {
            ('Abc', Point.objects.get(
                point_number=1, image=self.img1).pk, self.img1.pk),
        })

    def test_skipped_filenames_csv(self):
        """
        The CSV can have filenames that we don't recognize. Those rows
        will just be ignored.
        """
        rows = [
            ['Name', 'Column', 'Row', 'Label'],
            ['1.png', 50, 50, 'A'],
            ['4.png', 60, 40, 'B'],
        ]
        csv_file = self.make_csv_file('A.csv', rows)
        preview_response = self.preview_csv_annotations(
            self.user, self.source, csv_file)
        upload_response = self.upload_annotations(self.user, self.source)

        self.check_skipped_filenames(preview_response, upload_response)

    def test_skipped_filenames_cpc(self):
        """
        There can be CPCs corresponding to filenames that we don't recognize.
        Those CPCs will just be ignored.
        """
        cpc_files = [
            self.make_cpc_file(
                '1.cpc',
                r"C:\My Photos\2017-05-13 GBR\1.png", [
                    (49*15, 49*15, 'A')]),
            self.make_cpc_file(
                '4.cpc',
                r"C:\My Photos\2017-05-13 GBR\4.png", [
                    (59*15, 39*15, 'B')]),
        ]
        preview_response = self.preview_cpc_annotations(
            self.user, self.source, cpc_files)
        upload_response = self.upload_annotations(self.user, self.source)

        self.check_skipped_filenames(preview_response, upload_response)

    def check_skipped_filenames(self, preview_response, upload_response):

        self.assertDictEqual(
            preview_response.json(),
            dict(
                success=True,
                previewTable=[
                    dict(
                        name=self.img1.metadata.name,
                        link=reverse(
                            'annotation_tool',
                            kwargs=dict(image_id=self.img1.pk)),
                        createInfo="Will create 1 points, 1 annotations",
                    ),
                ],
                previewDetails=dict(
                    numImages=1,
                    totalPoints=1,
                    totalAnnotations=1,
                    numImagesWithExistingAnnotations=0,
                ),
            ),
        )

        self.assertDictEqual(upload_response.json(), dict(success=True))

        values_set = set(
            Point.objects.filter(image__in=[self.img1])
            .values_list('column', 'row', 'point_number', 'image_id'))
        self.assertSetEqual(values_set, {
            (50, 50, 1, self.img1.pk),
        })

        annotations = Annotation.objects.filter(image__in=[self.img1])
        values_set = set(
            (a.label_code, a.point.pk, a.image.pk)
            for a in annotations
        )
        self.assertSetEqual(values_set, {
            ('A', Point.objects.get(
                point_number=1, image=self.img1).pk, self.img1.pk),
        })


class UploadAnnotationsMultipleSourcesTest(UploadAnnotationsBaseTest):
    """
    Test involving multiple sources.
    """
    @classmethod
    def setUpTestData(cls):
        super(UploadAnnotationsMultipleSourcesTest, cls).setUpTestData()

        cls.user = cls.create_user()
        cls.source = cls.create_source(cls.user)
        cls.source2 = cls.create_source(cls.user)

        labels = cls.create_labels(cls.user, ['A', 'B'], 'Group1')
        cls.create_labelset(cls.user, cls.source, labels)
        cls.create_labelset(cls.user, cls.source2, labels)

        cls.img1_s1 = cls.upload_image(
            cls.user, cls.source,
            image_options=dict(filename='1.png', width=100, height=100))
        cls.img1_s2 = cls.upload_image(
            cls.user, cls.source2,
            image_options=dict(filename='1.png', width=100, height=100))
        cls.img2_s2 = cls.upload_image(
            cls.user, cls.source2,
            image_options=dict(filename='2.png', width=100, height=100))

    def test_other_sources_unaffected_csv(self):
        """
        We shouldn't touch images of other sources which happen to have
        the same image names.
        """
        # Upload to source 2
        rows = [
            ['Name', 'Column', 'Row', 'Label'],
            ['1.png', 10, 10, 'B'],
            ['1.png', 20, 20, 'B'],
            ['2.png', 15, 15, 'A'],
            ['2.png', 25, 25, 'A'],
        ]
        csv_file = self.make_csv_file('A.csv', rows)
        self.preview_csv_annotations(self.user, self.source2, csv_file)
        self.upload_annotations(self.user, self.source2)

        # Upload to source 1
        rows = [
            ['Name', 'Column', 'Row', 'Label'],
            ['1.png', 50, 50, 'A'],
            # This image doesn't exist in source 1
            ['2.png', 60, 40, 'B'],
        ]
        csv_file = self.make_csv_file('B.csv', rows)
        preview_response = self.preview_csv_annotations(
            self.user, self.source, csv_file)
        upload_response = self.upload_annotations(self.user, self.source)

        self.check_other_sources_unaffected(preview_response, upload_response)

    def test_other_sources_unaffected_cpc(self):
        """
        We shouldn't touch images of other sources which happen to have
        the same image names.
        """
        # Upload to source 2
        cpc_files = [
            self.make_cpc_file(
                '1.cpc',
                r"C:\My Photos\2017-05-13 GBR\1.png", [
                    (9*15, 9*15, 'B'),
                    (19*15, 19*15, 'B')]),
            self.make_cpc_file(
                '2.cpc',
                r"C:\My Photos\2017-05-13 GBR\2.png", [
                    (14*15, 14*15, 'A'),
                    (24*15, 24*15, 'A')]),
        ]
        self.preview_cpc_annotations(self.user, self.source2, cpc_files)
        self.upload_annotations(self.user, self.source2)

        # Upload to source 1
        cpc_files = [
            self.make_cpc_file(
                '1.cpc',
                r"C:\My Photos\2017-05-13 GBR\1.png", [
                    (49*15, 49*15, 'A')]),
            # This image doesn't exist in source 1
            self.make_cpc_file(
                '2.cpc',
                r"C:\My Photos\2017-05-13 GBR\2.png", [
                    (59*15, 39*15, 'B')]),
        ]
        preview_response = self.preview_cpc_annotations(
            self.user, self.source, cpc_files)
        upload_response = self.upload_annotations(self.user, self.source)

        self.check_other_sources_unaffected(preview_response, upload_response)

    def check_other_sources_unaffected(
            self, preview_response, upload_response):

        # Check source 1 responses

        self.assertDictEqual(
            preview_response.json(),
            dict(
                success=True,
                previewTable=[
                    dict(
                        name=self.img1_s1.metadata.name,
                        link=reverse(
                            'annotation_tool',
                            kwargs=dict(image_id=self.img1_s1.pk)),
                        createInfo="Will create 1 points, 1 annotations",
                    ),
                ],
                previewDetails=dict(
                    numImages=1,
                    totalPoints=1,
                    totalAnnotations=1,
                    numImagesWithExistingAnnotations=0,
                ),
            ),
        )

        self.assertDictEqual(upload_response.json(), dict(success=True))

        # Check source 1 objects

        values_set = set(
            Point.objects.filter(image__in=[self.img1_s1])
            .values_list('column', 'row', 'point_number', 'image_id'))
        self.assertSetEqual(values_set, {
            (50, 50, 1, self.img1_s1.pk),
        })

        annotations = Annotation.objects.filter(image__in=[self.img1_s1])
        values_set = set(
            (a.label_code, a.point.pk, a.image.pk)
            for a in annotations
        )
        self.assertSetEqual(values_set, {
            ('A', Point.objects.get(
                point_number=1, image=self.img1_s1).pk, self.img1_s1.pk),
        })

        # Check source 2 objects

        values_set = set(
            Point.objects.filter(image__in=[self.img1_s2, self.img2_s2])
            .values_list('column', 'row', 'point_number', 'image_id'))
        self.assertSetEqual(values_set, {
            (10, 10, 1, self.img1_s2.pk),
            (20, 20, 2, self.img1_s2.pk),
            (15, 15, 1, self.img2_s2.pk),
            (25, 25, 2, self.img2_s2.pk),
        })

        annotations = Annotation.objects.filter(
            image__in=[self.img1_s2, self.img2_s2])
        values_set = set(
            (a.label_code, a.point.pk, a.image.pk)
            for a in annotations
        )
        self.assertSetEqual(values_set, {
            ('B', Point.objects.get(
                point_number=1, image=self.img1_s2).pk, self.img1_s2.pk),
            ('B', Point.objects.get(
                point_number=2, image=self.img1_s2).pk, self.img1_s2.pk),
            ('A', Point.objects.get(
                point_number=1, image=self.img2_s2).pk, self.img2_s2.pk),
            ('A', Point.objects.get(
                point_number=2, image=self.img2_s2).pk, self.img2_s2.pk),
        })


class UploadAnnotationsContentsTest(UploadAnnotationsBaseTest):
    """
    Annotation upload edge cases and error cases related to contents.
    """
    @classmethod
    def setUpTestData(cls):
        super(UploadAnnotationsContentsTest, cls).setUpTestData()

        cls.user = cls.create_user()
        cls.source = cls.create_source(cls.user)
        # Labels in labelset
        labels = cls.create_labels(cls.user, ['A', 'B'], 'Group1')
        cls.create_labelset(cls.user, cls.source, labels)
        # Label not in labelset
        cls.create_labels(cls.user, ['C'], 'Group1')

        cls.img1 = cls.upload_image(
            cls.user, cls.source,
            image_options=dict(filename='1.png', width=200, height=100))
        cls.img2 = cls.upload_image(
            cls.user, cls.source,
            image_options=dict(filename='2.png', width=100, height=200))

    def do_success_csv(self, point_data, expected_points_set):
        rows = [['1.png']+list(p) for p in point_data]
        if len(rows[0]) == 3:
            header_row = ['Name', 'Column', 'Row']
        else:
            header_row = ['Name', 'Column', 'Row', 'Label']
        csv_file = self.make_csv_file('A.csv', [header_row] + rows)
        self.preview_csv_annotations(self.user, self.source, csv_file)
        self.upload_annotations(self.user, self.source)

        values_set = set(
            Point.objects.filter(image__in=[self.img1])
            .values_list('column', 'row', 'point_number', 'image_id'))
        self.assertSetEqual(values_set, expected_points_set)

    def do_error_csv(self, point_data, expected_error):
        rows = [['1.png']+list(p) for p in point_data]
        if len(rows[0]) == 3:
            header_row = ['Name', 'Column', 'Row']
        else:
            header_row = ['Name', 'Column', 'Row', 'Label']
        csv_file = self.make_csv_file('A.csv', [header_row] + rows)
        preview_response = self.preview_csv_annotations(
            self.user, self.source, csv_file)

        self.assertDictEqual(
            preview_response.json(),
            dict(error=expected_error))

    def do_success_cpc(self, point_data, expected_points_set):
        if len(point_data[0]) == 2:
            point_data = [p+('',) for p in point_data]
        cpc_files = [
            self.make_cpc_file(
                '1.cpc', r"C:\My Photos\2017-05-13 GBR\1.png", point_data)]
        self.preview_cpc_annotations(self.user, self.source, cpc_files)
        self.upload_annotations(self.user, self.source)

        values_set = set(
            Point.objects.filter(image__in=[self.img1])
            .values_list('column', 'row', 'point_number', 'image_id'))
        self.assertSetEqual(values_set, expected_points_set)

    def do_error_cpc(self, point_data, expected_error):
        if len(point_data[0]) == 2:
            point_data = [p+('',) for p in point_data]
        cpc_files = [
            self.make_cpc_file(
                '1.cpc', r"C:\My Photos\2017-05-13 GBR\1.png", point_data)]
        preview_response = self.preview_cpc_annotations(
            self.user, self.source, cpc_files)

        self.assertDictEqual(
            preview_response.json(),
            dict(error=expected_error))

    def test_row_not_number_csv(self):
        """A row/col which can't be parsed as a number should result in an
        appropriate error message."""
        self.do_error_csv(
            [(50, 'abc')],
            "Row value is not a positive integer: abc")

    def test_row_not_number_cpc(self):
        self.do_error_cpc(
            [(49*15, '?.;')], (
                "From file 1.cpc, point 1:"
                " Row value is not an integer in the accepted range: ?.;"))

    def test_column_not_number_csv(self):
        self.do_error_csv(
            [('1abc', 50)],
            "Column value is not a positive integer: 1abc")

    def test_column_not_number_cpc(self):
        self.do_error_cpc(
            [('abc2', 49*15)], (
                "From file 1.cpc, point 1:"
                " Column value is not an integer in the accepted range: abc2"))

    def test_row_is_float_csv(self):
        """A row/col which can't be parsed as an integer should result in an
        appropriate error message."""
        self.do_error_csv(
            [(50, 40.8)],
            "Row value is not a positive integer: 40.8")

    def test_row_is_float_cpc(self):
        self.do_error_cpc(
            [(49*15, 39*15+0.8)], (
                "From file 1.cpc, point 1:"
                " Row value is not an integer in the accepted range: 585.8"))

    def test_column_is_float_csv(self):
        self.do_error_csv(
            [(50.88, 40)],
            "Column value is not a positive integer: 50.88")

    def test_column_is_float_cpc(self):
        self.do_error_cpc(
            [(49*15+0.88, 39*15)], (
                "From file 1.cpc, point 1:"
                " Column value is not an integer in the accepted range:"
                " 735.88"))

    def test_row_minimum_value_csv(self):
        """Minimum acceptable row value."""
        self.do_success_csv(
            [(50, 1)],
            {(50, 1, 1, self.img1.pk)})

    def test_row_minimum_value_cpc(self):
        self.do_success_cpc(
            [(49*15, 0)],
            {(50, 1, 1, self.img1.pk)})

    def test_column_minimum_value_csv(self):
        self.do_success_csv(
            [(1, 40)],
            {(1, 40, 1, self.img1.pk)})

    def test_column_minimum_value_cpc(self):
        self.do_success_cpc(
            [(0, 39*15)],
            {(1, 40, 1, self.img1.pk)})

    def test_row_too_small_csv(self):
        """Below the minimum acceptable row value."""
        self.do_error_csv(
            [(50, 0)],
            "Row value is not a positive integer: 0")

    def test_row_too_small_cpc(self):
        self.do_error_cpc(
            [(49*15, -1)], (
                "From file 1.cpc, point 1:"
                " Row value is not an integer in the accepted range: -1"))

    def test_column_too_small_csv(self):
        self.do_error_csv(
            [(0, 50)],
            "Column value is not a positive integer: 0")

    def test_column_too_small_cpc(self):
        self.do_error_cpc(
            [(-1, 49*15)], (
                "From file 1.cpc, point 1:"
                " Column value is not an integer in the accepted range: -1"))

    def test_row_maximum_value_csv(self):
        """Maximum acceptable row value given the image dimensions."""
        self.do_success_csv(
            [(50, 100)],
            {(50, 100, 1, self.img1.pk)})

    def test_row_maximum_value_cpc(self):
        self.do_success_cpc(
            [(49*15, 99*15)],
            {(50, 100, 1, self.img1.pk)})

    def test_column_maximum_value_csv(self):
        self.do_success_csv(
            [(200, 40)],
            {(200, 40, 1, self.img1.pk)})

    def test_column_maximum_value_cpc(self):
        self.do_success_cpc(
            [(199*15, 39*15)],
            {(200, 40, 1, self.img1.pk)})

    def test_row_too_large_csv(self):
        """Above the maximum acceptable row value given the
        image dimensions."""
        self.do_error_csv(
            [(50, 101)], (
                "Row value of 101 is too large for image 1.png,"
                " which has dimensions 200 x 100"))

    def test_row_too_large_cpc(self):
        self.do_error_cpc(
            [(49*15, 100*15)], (
                "From file 1.cpc, point 1:"
                " Row value of 1500 corresponds to pixel 101."
                " This is too large"
                " for image 1.png, which has dimensions"
                " 200 x 100."))

    def test_column_too_large_csv(self):
        self.do_error_csv(
            [(201, 50)], (
                "Column value of 201 is too large for image 1.png,"
                " which has dimensions 200 x 100"))

    def test_column_too_large_cpc(self):
        self.do_error_cpc(
            [(200*15, 49*15)], (
                "From file 1.cpc, point 1:"
                " Column value of 3000 corresponds to pixel 201."
                " This is too large"
                " for image 1.png, which has dimensions"
                " 200 x 100."))

    def test_multiple_points_same_row_column_csv(self):
        """
        More than one point in the same image on the exact same position
        (same row and same column) should not be allowed.
        """
        self.do_error_csv(
            [(150, 90), (20, 20), (150, 90)], (
                "Image 1.png has multiple points on the same position:"
                " row 90, column 150"))

    def test_multiple_points_same_row_column_cpc(self):
        # These CPC file values for points 1 and 3
        # are different, but they map to the same pixel.
        self.do_error_cpc(
            [(149*15-2, 89*15-2), (19*15, 19*15), (149*15+2, 89*15+2)], (
                "From file 1.cpc:"
                " Points 1 and 3 are on the same"
                " pixel position:"
                " row 90, column 150"))

    def test_label_not_in_labelset_csv(self):
        self.do_error_csv(
            [(150, 90, 'B'), (20, 20, 'C')],
            "No label of code C found in this source's labelset")

    def test_label_not_in_labelset_cpc(self):
        self.do_error_cpc(
            [(149*15, 89*15, 'B'), (19*15, 19*15, 'C')], (
                "From file 1.cpc, point 2:"
                " No label of code C found in this source's labelset"))

    def test_no_specified_images_found_in_source_csv(self):
        """
        The import data has no filenames that can be found in the source.
        """
        csv_file = self.make_csv_file('A.csv', [
            ['Name', 'Column', 'Row'],
            ['3.png', 50, 50],
            ['4.png', 60, 40]])
        preview_response = self.preview_csv_annotations(
            self.user, self.source, csv_file)

        self.assertDictEqual(
            preview_response.json(),
            dict(
                error="No matching image names found in the source",
            ),
        )

    def test_no_specified_images_found_in_source_cpc(self):
        cpc_files = [
            self.make_cpc_file(
                '3.cpc', r"C:\My Photos\2017-05-13 GBR\3.png", [
                    (49*15, 49*15, '')]),
            self.make_cpc_file(
                '4.cpc', r"C:\My Photos\2017-05-13 GBR\4.png", [
                    (59*15, 39*15, '')]),
        ]
        preview_response = self.preview_cpc_annotations(
            self.user, self.source, cpc_files)

        self.assertDictEqual(
            preview_response.json(),
            dict(
                error="No matching image names found in the source",
            ),
        )


class UploadAnnotationsFormatTest(UploadAnnotationsBaseTest):
    """
    Tests (mostly error cases) related to file format, which apply to both CSV
    and CPC.
    """
    @classmethod
    def setUpTestData(cls):
        super(UploadAnnotationsFormatTest, cls).setUpTestData()

        cls.user = cls.create_user()
        cls.source = cls.create_source(cls.user)
        labels = cls.create_labels(cls.user, ['A', 'い'], 'Group1')
        cls.create_labelset(cls.user, cls.source, labels)

        cls.img1 = cls.upload_image(
            cls.user, cls.source,
            image_options=dict(filename='1.png', width=100, height=100))
        cls.imgA = cls.upload_image(
            cls.user, cls.source,
            image_options=dict(filename='あ.png', width=100, height=100))

    def check(self, preview_response, upload_response, img, label_code):

        self.assertDictEqual(
            preview_response.json(),
            dict(
                success=True,
                previewTable=[
                    dict(
                        name=img.metadata.name,
                        link=reverse(
                            'annotation_tool',
                            kwargs=dict(image_id=img.pk)),
                        createInfo="Will create 1 points, 1 annotations",
                    ),
                ],
                previewDetails=dict(
                    numImages=1,
                    totalPoints=1,
                    totalAnnotations=1,
                    numImagesWithExistingAnnotations=0,
                ),
            ),
        )

        self.assertDictEqual(upload_response.json(), dict(success=True))

        values_set = set(
            Point.objects.filter(image__in=[img])
            .values_list('column', 'row', 'point_number', 'image_id'))
        self.assertSetEqual(values_set, {
            (50, 50, 1, img.pk),
        })

        annotations = Annotation.objects.filter(image__in=[img])
        values_set = set(
            (a.label_code, a.point.pk, a.image.pk)
            for a in annotations
        )
        self.assertSetEqual(values_set, {
            (label_code, Point.objects.get(
                point_number=1, image=img).pk, img.pk),
        })

    def test_unicode_csv(self):
        content = (
            'Name,Column,Row,Label\n'
            'あ.png,50,50,い\n'
        )
        csv_file = ContentFile(content, name='A.csv')

        preview_response = self.preview_csv_annotations(
            self.user, self.source, csv_file)
        upload_response = self.upload_annotations(self.user, self.source)

        self.check(preview_response, upload_response, self.imgA, 'い')

    def test_unicode_cpc(self):
        """Don't know if CPC with non-ASCII is possible in practice, but
        might as well test that it works."""
        # The local image filepath gets path-manipulated at some point, and in
        # Python 2.x, pathlib2 doesn't support Unicode. So we'll only test
        # Unicode on the label code, not the filepath.
        cpc_files = [
            self.make_cpc_file(
                '1.cpc', r"C:\My Photos\2017-05-13 GBR\1.png",
                [(49*15, 49*15, 'い')]),
        ]
        preview_response = self.preview_cpc_annotations(
            self.user, self.source, cpc_files)
        upload_response = self.upload_annotations(self.user, self.source)

        self.check(preview_response, upload_response, self.img1, 'い')

    def test_crlf_csv(self):
        content = (
            'Name,Column,Row,Label\r\n'
            '1.png,50,50,A\r\n'
        )
        csv_file = ContentFile(content, name='A.csv')

        preview_response = self.preview_csv_annotations(
            self.user, self.source, csv_file)
        upload_response = self.upload_annotations(self.user, self.source)

        self.check(preview_response, upload_response, self.img1, 'A')

    def test_crlf_cpc(self):
        """Don't know if CPC with crlf newlines is possible in practice, but
        might as well test that it works."""
        cpc_file_lf = self.make_cpc_file(
            '1.cpc', r"C:\My Photos\2017-05-13 GBR\1.png",
            [(49*15, 49*15, 'A')])
        cpc_file_crlf_content = cpc_file_lf.read().replace('\n', '\r\n')
        cpc_files = [
            ContentFile(cpc_file_crlf_content, name='1.cpc'),
        ]
        preview_response = self.preview_cpc_annotations(
            self.user, self.source, cpc_files)
        upload_response = self.upload_annotations(self.user, self.source)

        self.check(preview_response, upload_response, self.img1, 'A')

    def test_cr_csv(self):
        content = (
            'Name,Column,Row,Label\r'
            '1.png,50,50,A\r'
        )
        csv_file = ContentFile(content, name='A.csv')

        preview_response = self.preview_csv_annotations(
            self.user, self.source, csv_file)
        upload_response = self.upload_annotations(self.user, self.source)

        self.check(preview_response, upload_response, self.img1, 'A')

    def test_cr_cpc(self):
        """Don't know if CPC with cr newlines is possible in practice, but
        might as well test that it works."""
        cpc_file_lf = self.make_cpc_file(
            '1.cpc', r"C:\My Photos\2017-05-13 GBR\1.png",
            [(49*15, 49*15, 'A')])
        cpc_file_crlf_content = cpc_file_lf.read().replace('\n', '\r')
        cpc_files = [
            ContentFile(cpc_file_crlf_content, name='1.cpc'),
        ]
        preview_response = self.preview_cpc_annotations(
            self.user, self.source, cpc_files)
        upload_response = self.upload_annotations(self.user, self.source)

        self.check(preview_response, upload_response, self.img1, 'A')

    def test_utf8_bom_csv(self):
        content = (
            codecs.BOM_UTF8.decode('utf-8') + 'Name,Column,Row,Label\n'
            '1.png,50,50,A\n'
        )
        csv_file = ContentFile(content, name='A.csv')

        preview_response = self.preview_csv_annotations(
            self.user, self.source, csv_file)
        upload_response = self.upload_annotations(self.user, self.source)

        self.check(preview_response, upload_response, self.img1, 'A')

    def test_utf8_bom_cpc(self):
        """Don't know if CPC with UTF-8 BOM is possible in practice, but
        might as well test that it works."""
        cpc_file_lf = self.make_cpc_file(
            '1.cpc', r"C:\My Photos\2017-05-13 GBR\1.png",
            [(49*15, 49*15, 'A')])
        cpc_file_crlf_content = (
            codecs.BOM_UTF8.decode('utf-8') + cpc_file_lf.read())
        cpc_files = [
            ContentFile(cpc_file_crlf_content, name='1.cpc'),
        ]
        preview_response = self.preview_cpc_annotations(
            self.user, self.source, cpc_files)
        upload_response = self.upload_annotations(self.user, self.source)

        self.check(preview_response, upload_response, self.img1, 'A')

    def test_empty_file_csv(self):
        csv_file = ContentFile('', name='A.csv')

        preview_response = self.preview_csv_annotations(
            self.user, self.source, csv_file)

        self.assertDictEqual(
            preview_response.json(),
            dict(error="The submitted file is empty."),
        )

    def test_empty_file_cpc(self):
        cpc_files = [
            ContentFile('', name='1.cpc')
        ]

        preview_response = self.preview_cpc_annotations(
            self.user, self.source, cpc_files)

        # TODO: The form's error handling should be improved so that the
        # message is "1.cpc: The submitted file is empty." instead.
        self.assertDictEqual(
            preview_response.json(),
            dict(error="The submitted file is empty."),
        )


class UploadAnnotationsCSVFormatTest(UploadAnnotationsBaseTest):
    """
    Tests (mostly error cases) specific to CSV format.
    """
    @classmethod
    def setUpTestData(cls):
        super(UploadAnnotationsCSVFormatTest, cls).setUpTestData()

        cls.user = cls.create_user()
        cls.source = cls.create_source(cls.user)
        labels = cls.create_labels(cls.user, ['A', 'B'], 'Group1')
        cls.create_labelset(cls.user, cls.source, labels)

        cls.img1 = cls.upload_image(
            cls.user, cls.source,
            image_options=dict(filename='1.png', width=100, height=100))

    def check(self, preview_response, upload_response):

        self.assertDictEqual(
            preview_response.json(),
            dict(
                success=True,
                previewTable=[
                    dict(
                        name=self.img1.metadata.name,
                        link=reverse(
                            'annotation_tool',
                            kwargs=dict(image_id=self.img1.pk)),
                        createInfo="Will create 1 points, 1 annotations",
                    ),
                ],
                previewDetails=dict(
                    numImages=1,
                    totalPoints=1,
                    totalAnnotations=1,
                    numImagesWithExistingAnnotations=0,
                ),
            ),
        )
        self.assertDictEqual(upload_response.json(), dict(success=True))

        values_set = set(
            Point.objects.filter(image__in=[self.img1])
            .values_list('column', 'row', 'point_number', 'image_id'))
        self.assertSetEqual(values_set, {
            (60, 40, 1, self.img1.pk),
        })

        annotations = Annotation.objects.filter(image__in=[self.img1])
        values_set = set(
            (a.label_code, a.point.pk, a.image.pk)
            for a in annotations
        )
        self.assertSetEqual(values_set, {
            ('A', Point.objects.get(
                point_number=1, image=self.img1).pk, self.img1.pk),
        })

    def test_skipped_csv_columns(self):
        """
        The CSV can have column names that we don't recognize. Those columns
        will just be ignored.
        """
        rows = [
            ['Name', 'Column', 'Row', 'Annotator', 'Label'],
            ['1.png', 60, 40, 'Jane', 'A'],
        ]
        csv_file = self.make_csv_file('A.csv', rows)
        preview_response = self.preview_csv_annotations(
            self.user, self.source, csv_file)
        upload_response = self.upload_annotations(self.user, self.source)

        self.check(preview_response, upload_response)

    def test_columns_different_order(self):
        """
        The CSV columns can be in a different order.
        """
        rows = [
            ['Row', 'Name', 'Label', 'Column'],
            [40, '1.png', 'A', 60],
        ]
        csv_file = self.make_csv_file('A.csv', rows)
        preview_response = self.preview_csv_annotations(
            self.user, self.source, csv_file)
        upload_response = self.upload_annotations(self.user, self.source)

        self.check(preview_response, upload_response)

    def test_columns_different_case(self):
        """
        The CSV column names can use different upper/lower case and still
        be matched to the expected column names.
        """
        rows = [
            ['name', 'coLUmN', 'ROW', 'Label'],
            ['1.png', 60, 40, 'A'],
        ]
        csv_file = self.make_csv_file('A.csv', rows)
        preview_response = self.preview_csv_annotations(
            self.user, self.source, csv_file)
        upload_response = self.upload_annotations(self.user, self.source)

        self.check(preview_response, upload_response)

    def test_no_name_column(self):
        """
        No CSV columns correspond to the name field.
        """
        rows = [
            ['Column', 'Row', 'Label'],
            [50, 50, 'A'],
            [60, 40, 'B'],
        ]
        csv_file = self.make_csv_file('A.csv', rows)
        preview_response = self.preview_csv_annotations(
            self.user, self.source, csv_file)

        self.assertDictEqual(
            preview_response.json(),
            dict(error="CSV must have a column called Name"),
        )

    def test_no_row_column(self):
        """
        No CSV columns correspond to the row field.
        """
        rows = [
            ['Name', 'Column', 'Label'],
            ['1.png', 50, 'A'],
            ['1.png', 60, 'B'],
        ]
        csv_file = self.make_csv_file('A.csv', rows)
        preview_response = self.preview_csv_annotations(
            self.user, self.source, csv_file)

        self.assertDictEqual(
            preview_response.json(),
            dict(error="CSV must have a column called Row"),
        )

    def test_no_column_column(self):
        """
        No CSV columns correspond to the column field.
        """
        rows = [
            ['Name', 'Row'],
            ['1.png', 50],
            ['1.png', 40],
        ]
        csv_file = self.make_csv_file('A.csv', rows)
        preview_response = self.preview_csv_annotations(
            self.user, self.source, csv_file)

        self.assertDictEqual(
            preview_response.json(),
            dict(error="CSV must have a column called Column"),
        )

    def test_missing_row(self):
        """
        A row is missing the row field.
        """
        rows = [
            ['Name', 'Column', 'Row'],
            ['1.png', 50, 50],
            ['1.png', 60, ''],
        ]
        csv_file = self.make_csv_file('A.csv', rows)
        preview_response = self.preview_csv_annotations(
            self.user, self.source, csv_file)

        self.assertDictEqual(
            preview_response.json(),
            dict(error="CSV row 3 is missing a Row value"),
        )

    def test_missing_column(self):
        """
        A row is missing the column field.
        """
        rows = [
            ['Name', 'Column', 'Row'],
            ['1.png', '', 50],
            ['1.png', 60, 40],
        ]
        csv_file = self.make_csv_file('A.csv', rows)
        preview_response = self.preview_csv_annotations(
            self.user, self.source, csv_file)

        self.assertDictEqual(
            preview_response.json(),
            dict(error="CSV row 2 is missing a Column value"),
        )

    def test_field_with_newline(self):
        """Field value with a newline character in it (within quotation marks).
        There's no reason to have this in any of the recognized columns, so we
        use an extra ignored column to test."""
        content = (
            'Name,Column,Row,Comments,Label'
            '\n1.png,60,40,"Here are\nsome comments.",A'
        )
        csv_file = ContentFile(content, name='A.csv')
        preview_response = self.preview_csv_annotations(
            self.user, self.source, csv_file)
        upload_response = self.upload_annotations(self.user, self.source)

        self.check(preview_response, upload_response)

    def test_field_with_surrounding_quotes(self):
        content = (
            'Name,Column,Row,Label'
            '\n"1.png","60","40","A"'
        )
        csv_file = ContentFile(content, name='A.csv')
        preview_response = self.preview_csv_annotations(
            self.user, self.source, csv_file)
        upload_response = self.upload_annotations(self.user, self.source)

        self.check(preview_response, upload_response)

    def test_field_with_surrounding_whitespace(self):
        """Strip whitespace surrounding the CSV values."""
        content = (
            'Name ,\tColumn\t,  Row,\tLabel    '
            '\n\t1.png,    60   , 40,A'
        )
        csv_file = ContentFile(content, name='A.csv')
        preview_response = self.preview_csv_annotations(
            self.user, self.source, csv_file)
        upload_response = self.upload_annotations(self.user, self.source)

        self.check(preview_response, upload_response)

    def test_non_csv(self):
        """
        Do at least basic detection of non-CSV files.
        """
        f = sample_image_as_file('A.jpg')
        preview_response = self.preview_csv_annotations(
            self.user, self.source, f)

        self.assertDictEqual(
            preview_response.json(),
            dict(
                error="The selected file is not a CSV file.",
            ),
        )


class UploadAnnotationsCPCFormatTest(UploadAnnotationsBaseTest):
    """
    Tests (mostly error cases) specific to CPC format.
    """
    @classmethod
    def setUpTestData(cls):
        super(UploadAnnotationsCPCFormatTest, cls).setUpTestData()

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
            '{n},{n}\n'.format(n=n*15) for n in range(1, 9+1)])
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
            '{n},{n}\n'.format(n=n*15) for n in range(1, 11+1)])
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
            '{n},{n}\n'.format(n=n*15) for n in range(1, 10+1)])
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
            '{n},{n}\n'.format(n=n*15) for n in range(1, 10+1)])
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
            '{n},{n}\n'.format(n=n*15) for n in range(1, 10+1)])
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


class UploadAnnotationsSaveCPCInfoTest(UploadAnnotationsBaseTest):
    """
    Tests saving of CPC file info when uploading CPCs.
    """
    @classmethod
    def setUpTestData(cls):
        super(UploadAnnotationsSaveCPCInfoTest, cls).setUpTestData()

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
