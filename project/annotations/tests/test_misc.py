from __future__ import division, unicode_literals
import math

from bs4 import BeautifulSoup
from django.urls import reverse

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
            '8',
            response_soup.find('input', dict(name='min_x')).attrs.get('value'))
        self.assertEqual(
            '25',
            response_soup.find('input', dict(name='max_x')).attrs.get('value'))
        self.assertEqual(
            '4',
            response_soup.find('input', dict(name='min_y')).attrs.get('value'))
        self.assertEqual(
            '46',
            response_soup.find('input', dict(name='max_y')).attrs.get('value'))

    def test_load_page_with_image_specific_annotation_area(self):
        # Set an image specific annotation area
        self.client.force_login(self.user)
        self.client.post(
            self.url, data=dict(min_x=9, max_x=37, min_y=1, max_y=19))

        # Ensure it's loaded on the next visit
        response = self.client.get(self.url)

        response_soup = BeautifulSoup(response.content, 'html.parser')
        self.assertEqual(
            '9',
            response_soup.find('input', dict(name='min_x')).attrs.get('value'))
        self.assertEqual(
            '37',
            response_soup.find('input', dict(name='max_x')).attrs.get('value'))
        self.assertEqual(
            '1',
            response_soup.find('input', dict(name='min_y')).attrs.get('value'))
        self.assertEqual(
            '19',
            response_soup.find('input', dict(name='max_y')).attrs.get('value'))

    def test_change_annotation_area(self):
        self.client.force_login(self.user)
        response = self.client.post(
            self.url, data=dict(min_x=9, max_x=37, min_y=1, max_y=19),
            follow=True)
        self.assertContains(response, "Annotation area successfully edited.")

        self.img.metadata.refresh_from_db()
        self.assertEqual(
            self.img.metadata.annotation_area,
            AnnotationAreaUtils.pixels_to_db_format(9, 37, 1, 19),
            msg="Annotation area should be successfully changed")

    def test_min_or_max_past_limits(self):
        self.client.force_login(self.user)

        response = self.client.post(
            self.url, data=dict(min_x=0, max_x=40, min_y=1, max_y=50))
        self.assertContains(response, "Please correct the errors below.")
        self.assertContains(
            response, "Ensure this value is greater than or equal to 1.")

        response = self.client.post(
            self.url, data=dict(min_x=1, max_x=41, min_y=1, max_y=50))
        self.assertContains(
            response, "Ensure this value is less than or equal to 40.")

        response = self.client.post(
            self.url, data=dict(min_x=1, max_x=40, min_y=0, max_y=50))
        self.assertContains(response, "Please correct the errors below.")
        self.assertContains(
            response, "Ensure this value is greater than or equal to 1.")

        response = self.client.post(
            self.url, data=dict(min_x=1, max_x=40, min_y=1, max_y=51))
        self.assertContains(
            response, "Ensure this value is less than or equal to 50.")

        response = self.client.post(
            self.url, data=dict(min_x=1, max_x=40, min_y=1, max_y=50),
            follow=True)
        self.assertContains(
            response, "Annotation area successfully edited.")

    # TODO: Test more error cases:
    # - min exceeds max
    # - non integers
    # - blank fields


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
        dict(min_x=1, max_x=20, min_y=1, max_y=30)
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
            points, dict(min_x=1, max_x=20, min_y=1, max_y=30))

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
                min_x=math.ceil((19/100)*40),
                max_x=math.ceil((62/100)*40),
                min_y=math.ceil((7/100)*50),
                max_y=math.ceil((90.2/100)*50)))

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
            data=dict(min_x=9, max_x=37, min_y=1, max_y=19))

        points = img.point_set.all()
        self.assertEqual(
            points.count(), 100,
            "Should generate the correct number of points")

        self.assertPointsAreInBounds(
            points, dict(min_x=9, max_x=37, min_y=1, max_y=19))

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
        for min_y, max_y in [(1,7), (8,15), (16,22), (23,30)]:
            for min_x, max_x in [(1,4), (5,8), (9,12), (13,16), (17,20)]:
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
        for min_y, max_y in [(3,8), (9,15), (16,21), (22,28)]:
            for min_x, max_x in [(4,5), (6,7), (8,9), (10,11), (12,13)]:
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
            data=dict(min_x=9, max_x=37, min_y=1, max_y=19))

        points = img.point_set.all()
        self.assertEqual(
            points.count(), 5*4*6,
            "Should generate the correct number of points")

        # Check the strata in order by point number. That's row by row,
        # top to bottom, left to right.
        point_index = 0
        for min_y, max_y in [(1,4), (5,9), (10,14), (15,19)]:
            for min_x, max_x in [(9,13), (14,19), (20,25), (26,31), (32,37)]:
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
        for y in [4, 11, 19, 26]:
            for x in [2, 6, 10, 14, 18]:
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
        for y in [5, 12, 18, 25]:
            for x in [4, 6, 8, 10, 12]:
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
            data=dict(min_x=9, max_x=37, min_y=1, max_y=19))

        points = img.point_set.all()
        self.assertEqual(
            points.count(), 5*4,
            "Should generate the correct number of points")

        # Check the points in order by point number. That's row by row,
        # top to bottom, left to right.
        point_index = 0
        for y in [2, 7, 12, 17]:
            for x in [11, 16, 22, 28, 34]:
                self.assertEqual(x, points[point_index].column)
                self.assertEqual(y, points[point_index].row)
                point_index += 1
