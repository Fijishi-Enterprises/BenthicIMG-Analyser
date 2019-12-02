# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import datetime

from django.core.files.base import ContentFile
from django.shortcuts import resolve_url
from django.test import override_settings

from annotations.models import Annotation
from export.tests.utils import BaseExportTest
from images.model_utils import PointGen
from lib.tests.utils import BasePermissionTest
from upload.tests.utils import UploadAnnotationsTestMixin


class PermissionTest(BasePermissionTest):

    def test_annotations_private_source(self):
        url = resolve_url(
            'export_annotations', self.private_source.pk)
        self.assertPermissionDenied(url, None)
        self.assertPermissionDenied(url, self.user_outsider)
        self.assertPermissionGranted(url, self.user_viewer)
        self.assertPermissionGranted(url, self.user_editor)
        self.assertPermissionGranted(url, self.user_admin)

    def test_annotations_public_source(self):
        url = resolve_url(
            'export_annotations', self.public_source.pk)
        self.assertPermissionGranted(url, None)
        self.assertPermissionGranted(url, self.user_outsider)
        self.assertPermissionGranted(url, self.user_viewer)
        self.assertPermissionGranted(url, self.user_editor)
        self.assertPermissionGranted(url, self.user_admin)


class ImageSetTest(BaseExportTest):
    """Test annotations export to CSV for different kinds of image subsets."""

    @classmethod
    def setUpTestData(cls):
        super(ImageSetTest, cls).setUpTestData()

        cls.user = cls.create_user()
        cls.source = cls.create_source(
            cls.user,
            point_generation_type=PointGen.Types.UNIFORM,
            number_of_cell_rows=1, number_of_cell_columns=2,
        )
        labels = cls.create_labels(cls.user, ['A', 'B'], 'GroupA')
        cls.create_labelset(cls.user, cls.source, labels)

    def test_all_images_single(self):
        """Export for 1 out of 1 images."""
        self.img1 = self.upload_image(
            self.user, self.source,
            dict(filename='1.jpg', width=400, height=300))
        self.add_annotations(self.user, self.img1, {1: 'A', 2: 'B'})

        post_data = self.default_search_params.copy()
        response = self.export_annotations(post_data)

        expected_lines = [
            'Name,Row,Column,Label',
            '1.jpg,150,100,A',
            '1.jpg,150,300,B',
        ]
        self.assert_csv_content_equal(response.content, expected_lines)

    def test_all_images_multiple(self):
        """Export for 3 out of 3 images."""
        self.img1 = self.upload_image(
            self.user, self.source,
            dict(filename='1.jpg', width=400, height=300))
        self.img2 = self.upload_image(
            self.user, self.source,
            dict(filename='2.jpg', width=400, height=400))
        self.img3 = self.upload_image(
            self.user, self.source,
            dict(filename='3.jpg', width=400, height=200))
        self.add_annotations(self.user, self.img1, {1: 'A', 2: 'B'})
        self.add_annotations(self.user, self.img2, {1: 'B', 2: 'A'})
        self.add_annotations(self.user, self.img3, {1: 'B', 2: 'B'})

        post_data = self.default_search_params.copy()
        response = self.export_annotations(post_data)

        expected_lines = [
            'Name,Row,Column,Label',
            '1.jpg,150,100,A',
            '1.jpg,150,300,B',
            '2.jpg,200,100,B',
            '2.jpg,200,300,A',
            '3.jpg,100,100,B',
            '3.jpg,100,300,B',
        ]
        self.assert_csv_content_equal(response.content, expected_lines)

    def test_image_subset_by_metadata(self):
        """Export for some, but not all, images."""
        self.img1 = self.upload_image(
            self.user, self.source,
            dict(filename='1.jpg', width=400, height=300))
        self.img2 = self.upload_image(
            self.user, self.source,
            dict(filename='2.jpg', width=400, height=400))
        self.img3 = self.upload_image(
            self.user, self.source,
            dict(filename='3.jpg', width=400, height=200))
        self.add_annotations(self.user, self.img1, {1: 'A', 2: 'B'})
        self.add_annotations(self.user, self.img2, {1: 'B', 2: 'A'})
        self.add_annotations(self.user, self.img3, {1: 'B', 2: 'B'})
        self.img1.metadata.aux1 = 'X'
        self.img1.metadata.save()
        self.img2.metadata.aux1 = 'Y'
        self.img2.metadata.save()
        self.img3.metadata.aux1 = 'X'
        self.img3.metadata.save()

        post_data = self.default_search_params.copy()
        post_data['aux1'] = 'X'
        response = self.export_annotations(post_data)

        expected_lines = [
            'Name,Row,Column,Label',
            '1.jpg,150,100,A',
            '1.jpg,150,300,B',
            '3.jpg,100,100,B',
            '3.jpg,100,300,B',
        ]
        self.assert_csv_content_equal(response.content, expected_lines)

    def test_image_subset_by_annotation_status(self):
        """Export for some, but not all, images. Different search criteria.
        Just a sanity check to ensure the image filtering is as complete
        as it should be."""
        self.img1 = self.upload_image(
            self.user, self.source,
            dict(filename='1.jpg', width=400, height=300))
        self.img2 = self.upload_image(
            self.user, self.source,
            dict(filename='2.jpg', width=400, height=400))
        self.img3 = self.upload_image(
            self.user, self.source,
            dict(filename='3.jpg', width=400, height=200))
        robot = self.create_robot(self.source)
        self.add_robot_annotations(robot, self.img1, {1: 'A', 2: 'A'})
        self.add_robot_annotations(robot, self.img2, {1: 'A', 2: 'A'})
        self.add_robot_annotations(robot, self.img3, {1: 'A', 2: 'A'})
        # Only images 2 and 3 become confirmed
        self.add_annotations(self.user, self.img2, {1: 'B', 2: 'A'})
        self.add_annotations(self.user, self.img3, {1: 'B', 2: 'B'})

        post_data = self.default_search_params.copy()
        post_data['annotation_status'] = 'confirmed'
        response = self.export_annotations(post_data)

        expected_lines = [
            'Name,Row,Column,Label',
            '2.jpg,200,100,B',
            '2.jpg,200,300,A',
            '3.jpg,100,100,B',
            '3.jpg,100,300,B',
        ]
        self.assert_csv_content_equal(response.content, expected_lines)

    def test_image_empty_set(self):
        """Export for 0 images."""
        self.img1 = self.upload_image(
            self.user, self.source,
            dict(filename='1.jpg', width=400, height=300))
        self.add_annotations(self.user, self.img1, {1: 'A', 2: 'B'})

        post_data = self.default_search_params.copy()
        post_data['image_name'] = '5.jpg'
        response = self.export_annotations(post_data)

        expected_lines = [
            'Name,Row,Column,Label',
        ]
        self.assert_csv_content_equal(response.content, expected_lines)


class AnnotationStatusTest(BaseExportTest):
    """Test annotations export to CSV for images of various annotation
    statuses."""

    @classmethod
    def setUpTestData(cls):
        super(AnnotationStatusTest, cls).setUpTestData()

        cls.user = cls.create_user()
        cls.source = cls.create_source(
            cls.user,
            point_generation_type=PointGen.Types.UNIFORM,
            number_of_cell_rows=1, number_of_cell_columns=2,
        )
        labels = cls.create_labels(cls.user, ['A', 'B'], 'GroupA')
        cls.create_labelset(cls.user, cls.source, labels)

        cls.img1 = cls.upload_image(
            cls.user, cls.source,
            dict(filename='1.jpg', width=400, height=300))

    def test_not_annotated(self):
        response = self.export_annotations(self.default_search_params)

        expected_lines = [
            'Name,Row,Column,Label',
        ]
        self.assert_csv_content_equal(response.content, expected_lines)

    def test_partially_annotated(self):
        self.add_annotations(self.user, self.img1, {1: 'B'})
        response = self.export_annotations(self.default_search_params)

        expected_lines = [
            'Name,Row,Column,Label',
            '1.jpg,150,100,B',
        ]
        self.assert_csv_content_equal(response.content, expected_lines)

    def test_fully_annotated(self):
        self.add_annotations(self.user, self.img1, {1: 'B', 2: 'A'})
        response = self.export_annotations(self.default_search_params)

        expected_lines = [
            'Name,Row,Column,Label',
            '1.jpg,150,100,B',
            '1.jpg,150,300,A',
        ]
        self.assert_csv_content_equal(response.content, expected_lines)

    def test_machine_annotated(self):
        robot = self.create_robot(self.source)
        self.add_robot_annotations(robot, self.img1, {1: 'B', 2: 'A'})
        response = self.export_annotations(self.default_search_params)

        expected_lines = [
            'Name,Row,Column,Label',
            '1.jpg,150,100,B',
            '1.jpg,150,300,A',
        ]
        self.assert_csv_content_equal(response.content, expected_lines)

    def test_part_machine_part_manual(self):
        robot = self.create_robot(self.source)
        self.add_robot_annotations(robot, self.img1, {1: 'B', 2: 'A'})
        self.add_annotations(self.user, self.img1, {2: 'A'})
        response = self.export_annotations(self.default_search_params)

        expected_lines = [
            'Name,Row,Column,Label',
            '1.jpg,150,100,B',
            '1.jpg,150,300,A',
        ]
        self.assert_csv_content_equal(response.content, expected_lines)


class AnnotatorInfoColumnsTest(BaseExportTest, UploadAnnotationsTestMixin):
    """Test the optional annotation info columns."""

    @classmethod
    def setUpTestData(cls):
        super(AnnotatorInfoColumnsTest, cls).setUpTestData()

        cls.user = cls.create_user()
        cls.source = cls.create_source(
            cls.user,
            point_generation_type=PointGen.Types.UNIFORM,
            number_of_cell_rows=1, number_of_cell_columns=1,
        )
        labels = cls.create_labels(cls.user, ['A', 'B'], 'GroupA')
        cls.create_labelset(cls.user, cls.source, labels)

        cls.img1 = cls.upload_image(
            cls.user, cls.source,
            dict(filename='1.jpg', width=400, height=300))

    def test_user_annotation(self):
        self.add_annotations(self.user, self.img1, {1: 'B'})
        post_data = self.default_search_params.copy()
        post_data['optional_columns'] = ['annotator_info']
        response = self.export_annotations(post_data)

        annotation_date = \
            Annotation.objects.get(image=self.img1).annotation_date
        date_str = annotation_date.strftime('%Y-%m-%d %H:%M:%S+00:00')

        expected_lines = [
            'Name,Row,Column,Label,Annotator,Date annotated',
            '1.jpg,150,200,B,{username},{date}'.format(
                username=self.user.username, date=date_str),
        ]
        self.assert_csv_content_equal(response.content, expected_lines)

    def test_imported_annotation(self):
        # Import an annotation
        rows = [
            ['Name', 'Row', 'Column', 'Label'],
            ['1.jpg', 50, 70, 'B'],
        ]
        csv_file = self.make_csv_file('A.csv', rows)
        self.preview_csv_annotations(
            self.user, self.source, csv_file)
        self.upload_annotations(self.user, self.source)

        post_data = self.default_search_params.copy()
        post_data['optional_columns'] = ['annotator_info']
        response = self.export_annotations(post_data)

        annotation_date = \
            Annotation.objects.get(image=self.img1).annotation_date
        date_str = annotation_date.strftime('%Y-%m-%d %H:%M:%S+00:00')

        expected_lines = [
            'Name,Row,Column,Label,Annotator,Date annotated',
            '1.jpg,50,70,B,Imported,{date}'.format(date=date_str),
        ]
        self.assert_csv_content_equal(response.content, expected_lines)

    def test_machine_annotation(self):
        robot = self.create_robot(self.source)
        self.add_robot_annotations(robot, self.img1, {1: 'B'})
        post_data = self.default_search_params.copy()
        post_data['optional_columns'] = ['annotator_info']
        response = self.export_annotations(post_data)

        annotation_date = \
            Annotation.objects.get(image=self.img1).annotation_date
        date_str = annotation_date.strftime('%Y-%m-%d %H:%M:%S+00:00')

        expected_lines = [
            'Name,Row,Column,Label,Annotator,Date annotated',
            '1.jpg,150,200,B,robot,{date}'.format(date=date_str),
        ]
        self.assert_csv_content_equal(response.content, expected_lines)


class MachineSuggestionColumnsTest(BaseExportTest):
    """Test the optional machine suggestion columns."""

    @classmethod
    def setUpTestData(cls):
        super(MachineSuggestionColumnsTest, cls).setUpTestData()

        cls.user = cls.create_user()
        cls.source = cls.create_source(
            cls.user,
            point_generation_type=PointGen.Types.UNIFORM,
            number_of_cell_rows=1, number_of_cell_columns=1,
        )
        labels = cls.create_labels(cls.user, ['A', 'B'], 'GroupA')
        cls.create_labelset(cls.user, cls.source, labels)

        cls.img1 = cls.upload_image(
            cls.user, cls.source,
            dict(filename='1.jpg', width=400, height=300))

    @override_settings(NBR_SCORES_PER_ANNOTATION=2)
    def test_blank(self):
        self.add_annotations(self.user, self.img1, {1: 'B'})
        post_data = self.default_search_params.copy()
        post_data['optional_columns'] = ['machine_suggestions']
        response = self.export_annotations(post_data)

        expected_lines = [
            'Name,Row,Column,Label'
            ',Machine suggestion 1,Machine confidence 1'
            ',Machine suggestion 2,Machine confidence 2',
            '1.jpg,150,200,B,,,,',
        ]
        self.assert_csv_content_equal(response.content, expected_lines)

    @override_settings(NBR_SCORES_PER_ANNOTATION=2)
    def test_all_suggestions_filled(self):
        robot = self.create_robot(self.source)
        # Normally we don't make assumptions on how add_robot_annotations()
        # assigns confidences after the first one, but since we only have 2
        # labels in the labelset, it should be safe to assume confidences of
        # 60 and 40 if we pass a top score of 60.
        self.add_robot_annotations(robot, self.img1, {1: ('B', 60)})

        post_data = self.default_search_params.copy()
        post_data['optional_columns'] = ['machine_suggestions']
        response = self.export_annotations(post_data)

        expected_lines = [
            'Name,Row,Column,Label'
            ',Machine suggestion 1,Machine confidence 1'
            ',Machine suggestion 2,Machine confidence 2',
            '1.jpg,150,200,B,B,60,A,40',
        ]
        self.assert_csv_content_equal(response.content, expected_lines)

    @override_settings(NBR_SCORES_PER_ANNOTATION=3)
    def test_some_suggestions_filled(self):
        robot = self.create_robot(self.source)
        # As before, we're assuming this gets confidences of 60 and 40.
        self.add_robot_annotations(robot, self.img1, {1: ('B', 60)})

        post_data = self.default_search_params.copy()
        post_data['optional_columns'] = ['machine_suggestions']
        response = self.export_annotations(post_data)

        expected_lines = [
            'Name,Row,Column,Label'
            ',Machine suggestion 1,Machine confidence 1'
            ',Machine suggestion 2,Machine confidence 2'
            ',Machine suggestion 3,Machine confidence 3',
            '1.jpg,150,200,B,B,60,A,40,,',
        ]
        self.assert_csv_content_equal(response.content, expected_lines)


class MetadataAuxColumnsTest(BaseExportTest):
    """Test the optional aux. metadata columns."""

    @classmethod
    def setUpTestData(cls):
        super(MetadataAuxColumnsTest, cls).setUpTestData()

        cls.user = cls.create_user()
        cls.source = cls.create_source(
            cls.user,
            point_generation_type=PointGen.Types.UNIFORM,
            number_of_cell_rows=1, number_of_cell_columns=1,
        )
        labels = cls.create_labels(cls.user, ['A', 'B'], 'GroupA')
        cls.create_labelset(cls.user, cls.source, labels)

        cls.img1 = cls.upload_image(
            cls.user, cls.source,
            dict(filename='1.jpg', width=400, height=300))

    def test_blank(self):
        self.add_annotations(self.user, self.img1, {1: 'B'})
        post_data = self.default_search_params.copy()
        post_data['optional_columns'] = ['metadata_date_aux']
        response = self.export_annotations(post_data)

        expected_lines = [
            'Name,Date,Aux1,Aux2,Aux3,Aux4,Aux5,Row,Column,Label',
            '1.jpg,,,,,,,150,200,B',
        ]
        self.assert_csv_content_equal(response.content, expected_lines)

    def test_filled(self):
        self.img1.metadata.photo_date = datetime.date(2001, 2, 3)
        self.img1.metadata.aux1 = "Site A"
        self.img1.metadata.aux2 = "Transect 1-2"
        self.img1.metadata.aux3 = "Quadrant 5"
        self.img1.metadata.save()
        self.add_annotations(self.user, self.img1, {1: 'B'})

        post_data = self.default_search_params.copy()
        post_data['optional_columns'] = ['metadata_date_aux']
        response = self.export_annotations(post_data)

        expected_lines = [
            'Name,Date,Aux1,Aux2,Aux3,Aux4,Aux5,Row,Column,Label',
            '1.jpg,2001-02-03,Site A,Transect 1-2,Quadrant 5,,,150,200,B',
        ]
        self.assert_csv_content_equal(response.content, expected_lines)

    def test_named_aux_fields(self):
        self.source.key1 = "Site"
        self.source.key2 = "Transect"
        self.source.key3 = "Quadrant"
        self.source.save()
        self.img1.metadata.photo_date = datetime.date(2001, 2, 3)
        self.img1.metadata.aux1 = "Site A"
        self.img1.metadata.aux2 = "Transect 1-2"
        self.img1.metadata.aux3 = "Quadrant 5"
        self.img1.metadata.save()
        self.add_annotations(self.user, self.img1, {1: 'B'})

        post_data = self.default_search_params.copy()
        post_data['optional_columns'] = ['metadata_date_aux']
        response = self.export_annotations(post_data)

        expected_lines = [
            'Name,Date,Site,Transect,Quadrant,Aux4,Aux5,Row,Column,Label',
            '1.jpg,2001-02-03,Site A,Transect 1-2,Quadrant 5,,,150,200,B',
        ]
        self.assert_csv_content_equal(response.content, expected_lines)


class MetadataOtherColumnsTest(BaseExportTest):
    """Test the optional other metadata columns."""

    @classmethod
    def setUpTestData(cls):
        super(MetadataOtherColumnsTest, cls).setUpTestData()

        cls.user = cls.create_user()
        cls.source = cls.create_source(
            cls.user,
            point_generation_type=PointGen.Types.UNIFORM,
            number_of_cell_rows=1, number_of_cell_columns=1,
        )
        labels = cls.create_labels(cls.user, ['A', 'B'], 'GroupA')
        cls.create_labelset(cls.user, cls.source, labels)

        cls.img1 = cls.upload_image(
            cls.user, cls.source,
            dict(filename='1.jpg', width=400, height=300))

    def test_blank(self):
        self.add_annotations(self.user, self.img1, {1: 'B'})
        post_data = self.default_search_params.copy()
        post_data['optional_columns'] = ['metadata_other']
        response = self.export_annotations(post_data)

        expected_lines = [
            'Name,Height (cm),Latitude,Longitude,Depth,Camera,Photographer'
            ',Water quality,Strobes,Framing gear used,White balance card'
            ',Comments,Row,Column,Label',
            '1.jpg,,,,,,,,,,,,150,200,B',
        ]
        self.assert_csv_content_equal(response.content, expected_lines)

    def test_filled(self):
        self.img1.metadata.height_in_cm = 40
        self.img1.metadata.latitude = "5.789"
        self.img1.metadata.longitude = "-50"
        self.img1.metadata.depth = "10m"
        self.img1.metadata.camera = "Nikon"
        self.img1.metadata.photographer = "John Doe"
        self.img1.metadata.water_quality = "Clear"
        self.img1.metadata.strobes = "White A"
        self.img1.metadata.framing = "Framing set C"
        self.img1.metadata.balance = "Card B"
        self.img1.metadata.comments = "Here are\nsome comments."
        self.img1.metadata.save()
        self.add_annotations(self.user, self.img1, {1: 'B'})

        post_data = self.default_search_params.copy()
        post_data['optional_columns'] = ['metadata_other']
        response = self.export_annotations(post_data)

        expected_lines = [
            'Name,Height (cm),Latitude,Longitude,Depth,Camera,Photographer'
            ',Water quality,Strobes,Framing gear used,White balance card'
            ',Comments,Row,Column,Label',
            '1.jpg,40,5.789,-50,10m,Nikon,John Doe'
            ',Clear,White A,Framing set C,Card B'
            ',"Here are\nsome comments.",150,200,B',
        ]
        self.assert_csv_content_equal(response.content, expected_lines)


class CombinationsOfOptionalColumnsTest(BaseExportTest):
    """Test combinations of optional column sets."""

    @classmethod
    def setUpTestData(cls):
        super(CombinationsOfOptionalColumnsTest, cls).setUpTestData()

        cls.user = cls.create_user()
        cls.source = cls.create_source(
            cls.user,
            point_generation_type=PointGen.Types.UNIFORM,
            number_of_cell_rows=1, number_of_cell_columns=1,
        )
        labels = cls.create_labels(cls.user, ['A', 'B'], 'GroupA')
        cls.create_labelset(cls.user, cls.source, labels)

        cls.img1 = cls.upload_image(
            cls.user, cls.source,
            dict(filename='1.jpg', width=400, height=300))

    def test_both_metadata_column_sets(self):
        self.source.key1 = "Site"
        self.source.key2 = "Transect"
        self.source.key3 = "Quadrant"
        self.source.save()
        self.img1.metadata.photo_date = datetime.date(2001, 2, 3)
        self.img1.metadata.aux1 = "Site A"
        self.img1.metadata.aux2 = "Transect 1-2"
        self.img1.metadata.aux3 = "Quadrant 5"
        self.img1.metadata.height_in_cm = 40
        self.img1.metadata.latitude = "5.789"
        self.img1.metadata.longitude = "-50"
        self.img1.metadata.depth = "10m"
        self.img1.metadata.camera = "Nikon"
        self.img1.metadata.photographer = "John Doe"
        self.img1.metadata.water_quality = "Clear"
        self.img1.metadata.strobes = "White A"
        self.img1.metadata.framing = "Framing set C"
        self.img1.metadata.balance = "Card B"
        self.img1.metadata.comments = "Here are\nsome comments."
        self.img1.metadata.save()
        self.add_annotations(self.user, self.img1, {1: 'B'})

        post_data = self.default_search_params.copy()
        post_data['optional_columns'] = ['metadata_date_aux', 'metadata_other']
        response = self.export_annotations(post_data)

        expected_lines = [
            'Name,Date,Site,Transect,Quadrant,Aux4,Aux5'
            ',Height (cm),Latitude,Longitude,Depth,Camera,Photographer'
            ',Water quality,Strobes,Framing gear used,White balance card'
            ',Comments,Row,Column,Label',
            '1.jpg,2001-02-03,Site A,Transect 1-2,Quadrant 5'
            ',,,40,5.789,-50,10m,Nikon,John Doe'
            ',Clear,White A,Framing set C,Card B'
            ',"Here are\nsome comments.",150,200,B',
        ]
        self.assert_csv_content_equal(response.content, expected_lines)

    def test_another_combination_of_two_sets(self):
        self.source.key1 = "Site"
        self.source.key2 = "Transect"
        self.source.key3 = "Quadrant"
        self.source.save()
        self.img1.metadata.photo_date = datetime.date(2001, 2, 3)
        self.img1.metadata.aux1 = "Site A"
        self.img1.metadata.aux2 = "Transect 1-2"
        self.img1.metadata.aux3 = "Quadrant 5"
        self.img1.metadata.save()
        self.add_annotations(self.user, self.img1, {1: 'B'})

        post_data = self.default_search_params.copy()
        post_data['optional_columns'] = ['annotator_info', 'metadata_date_aux']
        response = self.export_annotations(post_data)

        annotation_date = \
            Annotation.objects.get(image=self.img1).annotation_date
        date_str = annotation_date.strftime('%Y-%m-%d %H:%M:%S+00:00')

        expected_lines = [
            'Name,Date,Site,Transect,Quadrant,Aux4,Aux5'
            ',Row,Column,Label,Annotator,Date annotated',
            '1.jpg,2001-02-03,Site A,Transect 1-2,Quadrant 5,,'
            ',150,200,B,{username},{date}'.format(
                username=self.user.username, date=date_str),
        ]
        self.assert_csv_content_equal(response.content, expected_lines)

    @override_settings(NBR_SCORES_PER_ANNOTATION=2)
    def test_all_sets(self):
        self.source.key1 = "Site"
        self.source.key2 = "Transect"
        self.source.key3 = "Quadrant"
        self.source.save()
        self.img1.metadata.photo_date = datetime.date(2001, 2, 3)
        self.img1.metadata.aux1 = "Site A"
        self.img1.metadata.aux2 = "Transect 1-2"
        self.img1.metadata.aux3 = "Quadrant 5"
        self.img1.metadata.height_in_cm = 40
        self.img1.metadata.latitude = "5.789"
        self.img1.metadata.longitude = "-50"
        self.img1.metadata.depth = "10m"
        self.img1.metadata.camera = "Nikon"
        self.img1.metadata.photographer = "John Doe"
        self.img1.metadata.water_quality = "Clear"
        self.img1.metadata.strobes = "White A"
        self.img1.metadata.framing = "Framing set C"
        self.img1.metadata.balance = "Card B"
        self.img1.metadata.comments = "Here are\nsome comments."
        self.img1.metadata.save()

        robot = self.create_robot(self.source)
        self.add_robot_annotations(robot, self.img1, {1: ('B', 60)})
        self.add_annotations(self.user, self.img1, {1: 'B'})

        post_data = self.default_search_params.copy()
        post_data['optional_columns'] = [
            'annotator_info', 'machine_suggestions',
            'metadata_date_aux', 'metadata_other']
        response = self.export_annotations(post_data)

        annotation_date = \
            Annotation.objects.get(image=self.img1).annotation_date
        date_str = annotation_date.strftime('%Y-%m-%d %H:%M:%S+00:00')

        expected_lines = [
            'Name,Date,Site,Transect,Quadrant,Aux4,Aux5'
            ',Height (cm),Latitude,Longitude,Depth,Camera,Photographer'
            ',Water quality,Strobes,Framing gear used,White balance card'
            ',Comments,Row,Column,Label'
            ',Annotator,Date annotated'
            ',Machine suggestion 1,Machine confidence 1'
            ',Machine suggestion 2,Machine confidence 2',
            '1.jpg,2001-02-03,Site A,Transect 1-2,Quadrant 5,,'
            ',40,5.789,-50,10m,Nikon,John Doe'
            ',Clear,White A,Framing set C,Card B'
            ',"Here are\nsome comments.",150,200,B'
            ',{username},{date},B,60,A,40'.format(
                username=self.user.username, date=date_str),
        ]
        self.assert_csv_content_equal(response.content, expected_lines)


class UnicodeTest(BaseExportTest):
    """Test that non-ASCII characters don't cause problems."""

    @classmethod
    def setUpTestData(cls):
        super(UnicodeTest, cls).setUpTestData()

        cls.user = cls.create_user()
        cls.source = cls.create_source(
            cls.user,
            point_generation_type=PointGen.Types.UNIFORM,
            number_of_cell_rows=1, number_of_cell_columns=1,
        )
        labels = cls.create_labels(cls.user, ['A', 'い'], 'GroupA')
        cls.create_labelset(cls.user, cls.source, labels)

        cls.img1 = cls.upload_image(
            cls.user, cls.source,
            dict(filename='あ.jpg', width=400, height=300))

    def test(self):
        self.add_annotations(self.user, self.img1, {1: 'い'})

        post_data = self.default_search_params.copy()
        response = self.export_annotations(post_data)

        expected_lines = [
            'Name,Row,Column,Label',
            'あ.jpg,150,200,い',
        ]
        self.assert_csv_content_equal(
            response.content.decode('utf-8'), expected_lines)


class UploadAndExportSameDataTest(BaseExportTest):
    """Test that we can upload a CSV and then export the exact same CSV."""

    @classmethod
    def setUpTestData(cls):
        super(UploadAndExportSameDataTest, cls).setUpTestData()

        cls.user = cls.create_user()
        cls.source = cls.create_source(
            cls.user,
            point_generation_type=PointGen.Types.UNIFORM,
            number_of_cell_rows=1, number_of_cell_columns=1,
        )
        labels = cls.create_labels(cls.user, ['A', 'B'], 'GroupA')
        cls.create_labelset(cls.user, cls.source, labels)

    def test(self):
        self.img1 = self.upload_image(
            self.user, self.source,
            dict(filename='1.jpg', width=400, height=300))

        # Upload annotations
        content = ''
        csv_lines = [
            'Name,Row,Column,Label',
            '1.jpg,150,200,A',
        ]
        for line in csv_lines:
            content += (line + '\n')
        csv_file = ContentFile(content, name='annotations.csv')

        self.client.force_login(self.user)
        self.client.post(
            resolve_url('upload_annotations_csv_preview_ajax', self.source.pk),
            {'csv_file': csv_file},
        )
        self.client.post(
            resolve_url('upload_annotations_ajax', self.source.pk),
        )

        # Export annotations
        post_data = self.default_search_params.copy()
        response = self.export_annotations(post_data)

        self.assert_csv_content_equal(response.content, csv_lines)
