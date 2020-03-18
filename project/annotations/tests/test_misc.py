from __future__ import unicode_literals

from django.urls import reverse

from annotations.model_utils import AnnotationAreaUtils
from annotations.tasks import update_sitewide_annotation_count_task
from annotations.utils import get_sitewide_annotation_count
from images.model_utils import PointGen
from images.models import Source, Image, Point
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
            cls.user, visibility=Source.VisibilityTypes.PRIVATE)
        labels = cls.create_labels(cls.user, ['A', 'B'], 'GroupA')
        cls.create_labelset(cls.user, cls.source, labels)

        cls.img = cls.upload_image(cls.user, cls.source)
        cls.url = reverse('annotation_area_edit', args=[cls.img.pk])

    # TODO: Test correct field values when loading the page

    # TODO: Test submitting a new annotation area


class PointGenTest(ClientTest):
    """
    Test generation of annotation points.
    """
    @classmethod
    def setUpTestData(cls):
        super(PointGenTest, cls).setUpTestData()

        cls.user = cls.create_user()

        cls.source = cls.create_source(
            cls.user, visibility=Source.VisibilityTypes.PRIVATE,
            point_generation_type=PointGen.Types.SIMPLE,
            simple_number_of_points=20,
        )

    def pointgen_check(self, image_id):
        """
        Check that an image had annotation points generated as
        specified in the point generation method field.

        :param image_id: The id of the image to check.
        """
        img = Image.objects.get(pk=image_id)
        img_width = img.original_width
        img_height = img.original_height
        pointgen_args = PointGen.db_to_args_format(img.point_generation_method)

        points = Point.objects.filter(image=img)
        self.assertEqual(
            points.count(), pointgen_args['simple_number_of_points'])

        # Find the expected annotation area, expressed in pixels.
        d = AnnotationAreaUtils.db_format_to_numbers(
            img.metadata.annotation_area)
        annoarea_type = d.pop('type')
        if annoarea_type == AnnotationAreaUtils.TYPE_PERCENTAGES:
            area = AnnotationAreaUtils.percentages_to_pixels(
                width=img_width, height=img_height, **d)
        elif annoarea_type == AnnotationAreaUtils.TYPE_PIXELS:
            area = d
        elif annoarea_type == AnnotationAreaUtils.TYPE_IMPORTED:
            area = dict(min_x=1, max_x=img_width, min_y=1, max_y=img_height)
        else:
            raise ValueError("Unknown annotation area type.")

        # Some stuff that can be used when debugging:
        # print("{pointgen_method}".format(
        #     pointgen_method=img.point_gen_method_display()))
        # print("{annotation_area}".format(
        #     annotation_area=img.annotation_area_display()))
        # print("Image dimensions: {width} x {height} pixels".format(
        #     width=img_width, height=img_height))
        # print((
        #     "X bounds: ({min_x}, {max_x})"
        #     " Y bounds: ({min_y}, {max_y})").format(
        #         **area))

        for pt in points:
            self.assertTrue(area['min_x'] <= pt.column)
            self.assertTrue(pt.column <= area['max_x'])
            self.assertTrue(area['min_y'] <= pt.row)
            self.assertTrue(pt.row <= area['max_y'])

            # Can use when debugging
            # print "({col}, {row})".format(col=pt.column, row=pt.row)

    def test_pointgen_on_image_upload(self):
        """
        Test that annotation points are generated correctly upon an
        image upload.
        """
        img = self.upload_image(
            self.user, self.source, dict(width=10, height=20))
        self.pointgen_check(img.pk)

    # TODO: Test stratified random and uniform grid as well,
    # not just simple random.
    # TODO: Test unusual annotation areas: min and max very close or the same,
    # and decimal percentages.
