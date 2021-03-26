from __future__ import division, unicode_literals
import math
from unittest import skip

from bs4 import BeautifulSoup
from django.core.cache import cache
from django.urls import reverse
from django_migration_testcase import MigrationTest

from annotations.model_utils import AnnotationAreaUtils
from annotations.tasks import update_sitewide_annotation_count_task
from annotations.utils import get_sitewide_annotation_count
from images.model_utils import PointGen
from lib.tests.utils import BasePermissionTest, ClientTest


class PermissionTest(BasePermissionTest):
    """
    Test page and Ajax-submit permissions for misc. views.
    """
    def test_annotation_area_edit(self):
        img = self.upload_image(self.user, self.source)
        url = reverse('annotation_area_edit', args=[img.pk])
        template = 'annotations/annotation_area_edit.html'

        self.source_to_private()
        self.assertPermissionLevel(
            url, self.SOURCE_EDIT, template=template)
        self.source_to_public()
        self.assertPermissionLevel(
            url, self.SOURCE_EDIT, template=template)


class SitewideAnnotationCountTest(ClientTest):
    """
    Test the task which computes the site-wide annotation count.
    """
    @classmethod
    def setUpTestData(cls):
        super(SitewideAnnotationCountTest, cls).setUpTestData()
        cls.user = cls.create_user()
        cls.source = cls.create_source(cls.user)
        labels = cls.create_labels(cls.user, ['A', 'B'], "Group1")
        cls.create_labelset(cls.user, cls.source, labels)
        cls.img = cls.upload_image(cls.user, cls.source)
        cls.add_annotations(cls.user, cls.img, {1: 'A', 2: 'B', 3: 'A'})

    def setUp(self):
        super(SitewideAnnotationCountTest, self).setUp()

        # Sitewide annotation count gets cached after computation.
        # We must ensure subsequent tests can't interfere with each other.
        cache.clear()

    def test_set_on_demand(self):
        self.assertEqual(get_sitewide_annotation_count(), 3)

    def test_set_in_advance(self):
        update_sitewide_annotation_count_task.delay()
        self.assertEqual(get_sitewide_annotation_count(), 3)

    def test_set_then_update(self):
        update_sitewide_annotation_count_task.delay()
        self.assertEqual(get_sitewide_annotation_count(), 3)
        self.add_annotations(self.user, self.img, {4: 'B'})
        update_sitewide_annotation_count_task.delay()
        self.assertEqual(get_sitewide_annotation_count(), 4)

    def test_caching(self):
        update_sitewide_annotation_count_task.delay()
        self.assertEqual(get_sitewide_annotation_count(), 3)
        self.add_annotations(self.user, self.img, {4: 'B'})
        self.assertEqual(get_sitewide_annotation_count(), 3)


class AnnotationAreaEditTest(ClientTest):
    """
    Test the annotation area edit page.
    """
    @classmethod
    def setUpTestData(cls):
        super(AnnotationAreaEditTest, cls).setUpTestData()

        cls.user = cls.create_user()
        cls.source = cls.create_source(
            cls.user, min_x=19, max_x=62, min_y=7, max_y=90.2)

        cls.img = cls.upload_image(
            cls.user, cls.source, image_options=dict(width=40, height=50))
        cls.url = reverse('annotation_area_edit', args=[cls.img.pk])

    def test_load_page_with_source_annotation_area(self):
        self.client.force_login(self.user)
        response = self.client.get(self.url)

        response_soup = BeautifulSoup(response.content, 'html.parser')
        self.assertEqual(
            '7',
            response_soup.find('input', dict(name='min_x')).attrs.get('value'))
        self.assertEqual(
            '24',
            response_soup.find('input', dict(name='max_x')).attrs.get('value'))
        self.assertEqual(
            '3',
            response_soup.find('input', dict(name='min_y')).attrs.get('value'))
        self.assertEqual(
            '45',
            response_soup.find('input', dict(name='max_y')).attrs.get('value'))

    def test_load_page_with_image_specific_annotation_area(self):
        # Set an image specific annotation area
        self.client.force_login(self.user)
        self.client.post(
            self.url, data=dict(min_x=8, max_x=36, min_y=0, max_y=18))

        # Ensure it's loaded on the next visit
        response = self.client.get(self.url)

        response_soup = BeautifulSoup(response.content, 'html.parser')
        self.assertEqual(
            '8',
            response_soup.find('input', dict(name='min_x')).attrs.get('value'))
        self.assertEqual(
            '36',
            response_soup.find('input', dict(name='max_x')).attrs.get('value'))
        self.assertEqual(
            '0',
            response_soup.find('input', dict(name='min_y')).attrs.get('value'))
        self.assertEqual(
            '18',
            response_soup.find('input', dict(name='max_y')).attrs.get('value'))

    def test_change_annotation_area(self):
        self.client.force_login(self.user)
        response = self.client.post(
            self.url, data=dict(min_x=8, max_x=36, min_y=0, max_y=18),
            follow=True)
        self.assertContains(response, "Annotation area successfully edited.")

        self.img.metadata.refresh_from_db()
        self.assertEqual(
            self.img.metadata.annotation_area,
            AnnotationAreaUtils.pixels_to_db_format(8, 36, 0, 18),
            msg="Annotation area should be successfully changed")

    def test_min_or_max_past_limits(self):
        self.client.force_login(self.user)

        response = self.client.post(
            self.url, data=dict(min_x=-1, max_x=39, min_y=0, max_y=49))
        self.assertContains(response, "Please correct the errors below.")
        self.assertContains(
            response, "Ensure this value is greater than or equal to 0.")

        response = self.client.post(
            self.url, data=dict(min_x=0, max_x=40, min_y=0, max_y=49))
        self.assertContains(
            response, "Ensure this value is less than or equal to 39.")

        response = self.client.post(
            self.url, data=dict(min_x=0, max_x=39, min_y=-1, max_y=49))
        self.assertContains(response, "Please correct the errors below.")
        self.assertContains(
            response, "Ensure this value is greater than or equal to 0.")

        response = self.client.post(
            self.url, data=dict(min_x=0, max_x=39, min_y=0, max_y=50))
        self.assertContains(
            response, "Ensure this value is less than or equal to 49.")

        response = self.client.post(
            self.url, data=dict(min_x=0, max_x=39, min_y=0, max_y=49),
            follow=True)
        self.assertContains(
            response, "Annotation area successfully edited.")

    @skip(
        "There's a bug in the behavior here."
        " Need to fix that in the annotation area edit form.")
    def test_min_exceeds_max(self):
        self.client.force_login(self.user)

        response = self.client.post(
            self.url, data=dict(min_x=30, max_x=29, min_y=29, max_y=30))
        self.assertContains(response, "Please correct the errors below.")
        self.assertContains(
            response,
            "The right boundary x must be greater than or equal to"
            " the left boundary x.")

        response = self.client.post(
            self.url, data=dict(min_x=0, max_x=1, min_y=1, max_y=0))
        self.assertContains(
            response,
            "The bottom boundary y must be greater than or equal to"
            " the top boundary y.")

    def test_non_integers(self):
        self.client.force_login(self.user)

        response = self.client.post(
            self.url, data=dict(min_x=8, max_x=36, min_y=0, max_y='a'))
        self.assertContains(response, "Please correct the errors below.")
        self.assertContains(response, "Enter a whole number.")

        response = self.client.post(
            self.url, data=dict(min_x=8.28, max_x=36, min_y=0, max_y=18))
        self.assertContains(response, "Please correct the errors below.")
        self.assertContains(response, "Enter a whole number.")

    # TODO: Test blank fields


class PointGenTest(ClientTest):
    """
    Test generation of annotation points.
    """
    @classmethod
    def setUpTestData(cls):
        super(PointGenTest, cls).setUpTestData()

        cls.user = cls.create_user()

    def assertPointsAreInBounds(self, points, bounds):
        """
        Check that every Point in the given points array is within the
        bounds specified.
        bounds is a dict of pixel-position boundaries. For example,
        dict(min_x=0, max_x=19, min_y=0, max_y=29)
        """
        for pt in points:
            self.assertTrue(bounds['min_x'] <= pt.column)
            self.assertTrue(pt.column <= bounds['max_x'])
            self.assertTrue(bounds['min_y'] <= pt.row)
            self.assertTrue(pt.row <= bounds['max_y'])

    def test_simple_random_whole_image(self):
        source = self.create_source(
            self.user,
            point_generation_type=PointGen.Types.SIMPLE,
            simple_number_of_points=100,
            min_x=0, max_x=100, min_y=0, max_y=100)
        # Make the resolution small so that we have a good chance of
        # testing the annotation area boundaries.
        img = self.upload_image(
            self.user, source, image_options=dict(width=20, height=30))

        points = img.point_set.all()
        self.assertEqual(
            points.count(), 100,
            "Should generate the correct number of points")

        self.assertPointsAreInBounds(
            points, dict(min_x=0, max_x=19, min_y=0, max_y=29))

    def test_simple_random_source_annotation_area(self):
        source = self.create_source(
            self.user,
            point_generation_type=PointGen.Types.SIMPLE,
            simple_number_of_points=100,
            min_x=19, max_x=62, min_y=7, max_y=90.2)
        img = self.upload_image(
            self.user, source, image_options=dict(width=40, height=50))

        points = img.point_set.all()
        self.assertEqual(
            points.count(), 100,
            "Should generate the correct number of points")

        self.assertPointsAreInBounds(
            points, dict(
                min_x=math.floor((19/100)*40),
                max_x=math.floor((62/100)*40),
                min_y=math.floor((7/100)*50),
                max_y=math.floor((90.2/100)*50)))

    def test_simple_random_image_specific_annotation_area(self):
        source = self.create_source(
            self.user,
            point_generation_type=PointGen.Types.SIMPLE,
            simple_number_of_points=100)
        img = self.upload_image(
            self.user, source, image_options=dict(width=40, height=50))

        self.client.force_login(self.user)
        self.client.post(
            reverse('annotation_area_edit', args=[img.pk]),
            data=dict(min_x=8, max_x=36, min_y=0, max_y=18))

        points = img.point_set.all()
        self.assertEqual(
            points.count(), 100,
            "Should generate the correct number of points")

        self.assertPointsAreInBounds(
            points, dict(min_x=8, max_x=36, min_y=0, max_y=18))

    def test_stratified_random_whole_image(self):
        source = self.create_source(
            self.user,
            point_generation_type=PointGen.Types.STRATIFIED,
            number_of_cell_columns=5, number_of_cell_rows=4,
            stratified_points_per_cell=6,
            min_x=0, max_x=100, min_y=0, max_y=100)
        img = self.upload_image(
            self.user, source, image_options=dict(width=20, height=30))

        points = img.point_set.all().order_by('point_number')
        self.assertEqual(
            points.count(), 5*4*6,
            "Should generate the correct number of points")

        # Check the strata in order by point number. That's row by row,
        # top to bottom, left to right.
        point_index = 0
        for min_y, max_y in [(0,6), (7,14), (15,21), (22,29)]:
            for min_x, max_x in [(0,3), (4,7), (8,11), (12,15), (16,19)]:
                self.assertPointsAreInBounds(
                    points[point_index:point_index+6],
                    dict(min_x=min_x, max_x=max_x, min_y=min_y, max_y=max_y))
                point_index += 6

    def test_stratified_random_source_annotation_area(self):
        source = self.create_source(
            self.user,
            point_generation_type=PointGen.Types.STRATIFIED,
            number_of_cell_columns=5, number_of_cell_rows=4,
            stratified_points_per_cell=6,
            min_x=19, max_x=62, min_y=7, max_y=90.2)
        img = self.upload_image(
            self.user, source, image_options=dict(width=20, height=30))

        points = img.point_set.all().order_by('point_number')
        self.assertEqual(
            points.count(), 5*4*6,
            "Should generate the correct number of points")

        # Check the strata in order by point number. That's row by row,
        # top to bottom, left to right.
        point_index = 0
        for min_y, max_y in [(2,7), (8,14), (15,20), (21,27)]:
            for min_x, max_x in [(3,4), (5,6), (7,8), (9,10), (11,12)]:
                self.assertPointsAreInBounds(
                    points[point_index:point_index+6],
                    dict(min_x=min_x, max_x=max_x, min_y=min_y, max_y=max_y))
                point_index += 6

    def test_stratified_random_image_specific_annotation_area(self):
        source = self.create_source(
            self.user,
            point_generation_type=PointGen.Types.STRATIFIED,
            number_of_cell_columns=5, number_of_cell_rows=4,
            stratified_points_per_cell=6)
        img = self.upload_image(
            self.user, source, image_options=dict(width=40, height=50))

        self.client.force_login(self.user)
        self.client.post(
            reverse('annotation_area_edit', args=[img.pk]),
            data=dict(min_x=8, max_x=36, min_y=0, max_y=18))

        points = img.point_set.all()
        self.assertEqual(
            points.count(), 5*4*6,
            "Should generate the correct number of points")

        # Check the strata in order by point number. That's row by row,
        # top to bottom, left to right.
        point_index = 0
        for min_y, max_y in [(0,3), (4,8), (9,13), (14,18)]:
            for min_x, max_x in [(8,12), (13,18), (19,24), (25,30), (31,36)]:
                self.assertPointsAreInBounds(
                    points[point_index:point_index+6],
                    dict(min_x=min_x, max_x=max_x, min_y=min_y, max_y=max_y))
                point_index += 6

    def test_uniform_grid_whole_image(self):
        source = self.create_source(
            self.user,
            point_generation_type=PointGen.Types.UNIFORM,
            number_of_cell_columns=5, number_of_cell_rows=4,
            min_x=0, max_x=100, min_y=0, max_y=100)
        img = self.upload_image(
            self.user, source, image_options=dict(width=20, height=30))

        points = img.point_set.all().order_by('point_number')
        self.assertEqual(
            points.count(), 5*4,
            "Should generate the correct number of points")

        # Check the points in order by point number. That's row by row,
        # top to bottom, left to right.
        point_index = 0
        for y in [3, 10, 18, 25]:
            for x in [1, 5, 9, 13, 17]:
                self.assertEqual(x, points[point_index].column)
                self.assertEqual(y, points[point_index].row)
                point_index += 1

    def test_uniform_grid_source_annotation_area(self):
        source = self.create_source(
            self.user,
            point_generation_type=PointGen.Types.UNIFORM,
            number_of_cell_columns=5, number_of_cell_rows=4,
            min_x=19, max_x=62, min_y=7, max_y=90.2)
        img = self.upload_image(
            self.user, source, image_options=dict(width=20, height=30))

        points = img.point_set.all().order_by('point_number')
        self.assertEqual(
            points.count(), 5*4,
            "Should generate the correct number of points")

        # Check the points in order by point number. That's row by row,
        # top to bottom, left to right.
        point_index = 0
        for y in [4, 11, 17, 24]:
            for x in [3, 5, 7, 9, 11]:
                self.assertEqual(x, points[point_index].column)
                self.assertEqual(y, points[point_index].row)
                point_index += 1

    def test_uniform_grid_image_specific_annotation_area(self):
        source = self.create_source(
            self.user,
            point_generation_type=PointGen.Types.UNIFORM,
            number_of_cell_columns=5, number_of_cell_rows=4)
        img = self.upload_image(
            self.user, source, image_options=dict(width=40, height=50))

        self.client.force_login(self.user)
        self.client.post(
            reverse('annotation_area_edit', args=[img.pk]),
            data=dict(min_x=8, max_x=36, min_y=0, max_y=18))

        points = img.point_set.all()
        self.assertEqual(
            points.count(), 5*4,
            "Should generate the correct number of points")

        # Check the points in order by point number. That's row by row,
        # top to bottom, left to right.
        point_index = 0
        for y in [1, 6, 11, 16]:
            for x in [10, 15, 21, 27, 33]:
                self.assertEqual(x, points[point_index].column)
                self.assertEqual(y, points[point_index].row)
                point_index += 1


class ImageAnnotationInfoMigrationTest(MigrationTest):
    """
    Test porting from Image's annotation progress fields to the corresponding
    ImageAnnotationInfo fields.
    """

    before = [
        ('annotations', '0019_field_string_attributes_to_unicode'),
        ('images', '0031_remove_image_features'),
        ('labels', '0012_field_string_attributes_to_unicode'),
    ]
    after = [
        ('annotations', '0021_populate_imageannotationinfo'),
        ('images', '0033_remove_image_annotation_progress'),
    ]

    image_defaults = dict(
        original_width=100,
        original_height=100,
    )

    def test_port_annotation_progress_fields(self):
        Annotation = self.get_model_before('annotations.Annotation')
        Image = self.get_model_before('images.Image')
        Metadata = self.get_model_before('images.Metadata')
        Point = self.get_model_before('images.Point')
        Source = self.get_model_before('images.Source')
        Label = self.get_model_before('labels.Label')
        LabelGroup = self.get_model_before('labels.LabelGroup')

        source = Source.objects.create()

        # More than 1 Image
        image_1 = Image.objects.create(
            source=source, metadata=Metadata.objects.create(),
            **self.image_defaults)
        image_2 = Image.objects.create(
            source=source, metadata=Metadata.objects.create(),
            **self.image_defaults)

        # 2 Annotations on image_1, none on image_2
        Annotation.objects.create(
            point=Point.objects.create(
                image=image_1, point_number=1, row=10, column=20),
            label=Label.objects.create(
                group=LabelGroup.objects.create(name='1', code='1'),
                name='A', default_code='A'),
            image=image_1, source=source)
        annotation_2 = Annotation.objects.create(
            point=Point.objects.create(
                image=image_1, point_number=2, row=30, column=40),
            label=Label.objects.create(
                group=LabelGroup.objects.create(name='2', code='2'),
                name='B', default_code='B'),
            image=image_1, source=source)

        image_1.last_annotation = annotation_2
        image_1.confirmed = True
        image_1.save()
        image_2.last_annotation = None
        image_2.confirmed = False
        image_2.save()

        image_1_pk = image_1.pk
        image_2_pk = image_2.pk
        annotation_2_pk = annotation_2.pk

        # annoinfo attributes shouldn't exist yet
        self.assertRaises(AttributeError, getattr, image_1, 'annoinfo')
        self.assertRaises(AttributeError, getattr, image_2, 'annoinfo')

        self.run_migration()

        Image = self.get_model_after('images.Image')

        # annoinfo attributes should be filled in
        image_1 = Image.objects.get(pk=image_1_pk)
        self.assertEqual(image_1.annoinfo.last_annotation.pk, annotation_2_pk)
        self.assertEqual(image_1.annoinfo.confirmed, True)
        image_2 = Image.objects.get(pk=image_2_pk)
        self.assertEqual(image_2.annoinfo.last_annotation, None)
        self.assertEqual(image_2.annoinfo.confirmed, False)


class ImageAnnotationInfoBackwardsMigrationTest(MigrationTest):
    """
    Test porting from ImageAnnotationInfo's annotation progress fields
    back to the corresponding Image fields.
    """

    before = [
        ('labels', '0012_field_string_attributes_to_unicode'),
        ('annotations', '0021_populate_imageannotationinfo'),
        ('images', '0033_remove_image_annotation_progress'),
    ]
    after = [
        # Apparently, ordering here is important to make sure all migrations
        # get to run.
        ('images', '0031_remove_image_features'),
        ('annotations', '0019_field_string_attributes_to_unicode'),
    ]

    image_defaults = dict(
        original_width=100,
        original_height=100,
    )

    def test_port_annotation_progress_fields(self):
        Annotation = self.get_model_before('annotations.Annotation')
        ImageAnnotationInfo = self.get_model_before(
            'annotations.ImageAnnotationInfo')
        Image = self.get_model_before('images.Image')
        Metadata = self.get_model_before('images.Metadata')
        Point = self.get_model_before('images.Point')
        Source = self.get_model_before('images.Source')
        Label = self.get_model_before('labels.Label')
        LabelGroup = self.get_model_before('labels.LabelGroup')

        source = Source.objects.create()

        # More than 1 Image
        image_1 = Image.objects.create(
            source=source, metadata=Metadata.objects.create(),
            **self.image_defaults)
        image_2 = Image.objects.create(
            source=source, metadata=Metadata.objects.create(),
            **self.image_defaults)

        # 2 Annotations on image_1, none on image_2
        Annotation.objects.create(
            point=Point.objects.create(
                image=image_1, point_number=1, row=10, column=20),
            label=Label.objects.create(
                group=LabelGroup.objects.create(name='1', code='1'),
                name='A', default_code='A'),
            image=image_1, source=source)
        annotation_2 = Annotation.objects.create(
            point=Point.objects.create(
                image=image_1, point_number=2, row=30, column=40),
            label=Label.objects.create(
                group=LabelGroup.objects.create(name='2', code='2'),
                name='B', default_code='B'),
            image=image_1, source=source)

        ImageAnnotationInfo.objects.create(
            image=image_1, last_annotation=annotation_2, confirmed=True)
        ImageAnnotationInfo.objects.create(
            image=image_2, last_annotation=None, confirmed=False)

        image_1_pk = image_1.pk
        image_2_pk = image_2.pk
        annotation_2_pk = annotation_2.pk

        # Image attributes shouldn't exist yet
        self.assertRaises(AttributeError, getattr, image_1, 'confirmed')
        self.assertRaises(AttributeError, getattr, image_1, 'last_annotation')
        self.assertRaises(AttributeError, getattr, image_2, 'confirmed')
        self.assertRaises(AttributeError, getattr, image_2, 'last_annotation')

        self.run_migration()

        Image = self.get_model_after('images.Image')

        # Image attributes should be filled in
        image_1 = Image.objects.get(pk=image_1_pk)
        self.assertEqual(image_1.last_annotation.pk, annotation_2_pk)
        self.assertEqual(image_1.confirmed, True)
        image_2 = Image.objects.get(pk=image_2_pk)
        self.assertEqual(image_2.last_annotation, None)
        self.assertEqual(image_2.confirmed, False)

        # annoinfo attributes shouldn't exist anymore
        self.assertRaises(AttributeError, getattr, image_1, 'annoinfo')
        self.assertRaises(AttributeError, getattr, image_2, 'annoinfo')
