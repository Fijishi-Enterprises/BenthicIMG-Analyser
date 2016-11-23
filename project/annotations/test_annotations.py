from django.conf import settings
from django.core.urlresolvers import reverse
from annotations.model_utils import AnnotationAreaUtils
from images.model_utils import PointGen
from images.models import Source, Image, Point
from lib.test_utils import ClientTest


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

        cls.user_outsider = cls.create_user()
        cls.user_viewer = cls.create_user()
        cls.add_source_member(
            cls.user, cls.source, cls.user_viewer, Source.PermTypes.VIEW.code)
        cls.user_editor = cls.create_user()
        cls.add_source_member(
            cls.user, cls.source, cls.user_editor, Source.PermTypes.EDIT.code)

        cls.img = cls.upload_image(cls.user, cls.source)
        cls.url = reverse('annotation_area_edit', args=[cls.img.pk])

    def test_load_page_anonymous(self):
        """
        Load the page while logged out ->
        sorry, don't have permission.
        """
        response = self.client.get(self.url)
        self.assertStatusOK(response)
        self.assertTemplateUsed(response, self.PERMISSION_DENIED_TEMPLATE)

    def test_load_page_as_source_outsider(self):
        """
        Load the page as a user outside the source ->
        sorry, don't have permission.
        """
        self.client.force_login(self.user_outsider)
        response = self.client.get(self.url)
        self.assertStatusOK(response)
        self.assertTemplateUsed(response, self.PERMISSION_DENIED_TEMPLATE)

    def test_load_page_as_source_viewer(self):
        """
        Load the page as a source viewer ->
        sorry, don't have permission.
        """
        self.client.force_login(self.user_viewer)
        response = self.client.get(self.url)
        self.assertStatusOK(response)
        self.assertTemplateUsed(response, self.PERMISSION_DENIED_TEMPLATE)

    def test_load_page(self):
        self.client.force_login(self.user_editor)
        response = self.client.get(self.url)
        self.assertStatusOK(response)
        self.assertTemplateUsed(
            response, 'annotations/annotation_area_edit.html')

    # TODO: Test submitting a new annotation area


class AnnotationHistoryTest(ClientTest):
    """
    Test the annotation history page.
    """
    @classmethod
    def setUpTestData(cls):
        super(AnnotationHistoryTest, cls).setUpTestData()

        cls.user = cls.create_user()

        cls.source = cls.create_source(
            cls.user, visibility=Source.VisibilityTypes.PRIVATE,
            point_generation_type=PointGen.Types.SIMPLE,
            simple_number_of_points=3,
        )
        labels = cls.create_labels(cls.user, ['A', 'B'], 'GroupA')
        cls.create_labelset(cls.user, cls.source, labels)

        cls.user_outsider = cls.create_user()
        cls.user_viewer = cls.create_user()
        cls.add_source_member(
            cls.user, cls.source, cls.user_viewer, Source.PermTypes.VIEW.code)
        cls.user_editor = cls.create_user()
        cls.add_source_member(
            cls.user, cls.source, cls.user_editor, Source.PermTypes.EDIT.code)
        cls.user_editor2 = cls.create_user()
        cls.add_source_member(
            cls.user, cls.source, cls.user_editor2, Source.PermTypes.EDIT.code)

        cls.img = cls.upload_image(cls.user, cls.source)
        cls.url = reverse('annotation_history', args=[cls.img.pk])

    def test_load_page_anonymous(self):
        """
        Load the page while logged out ->
        sorry, don't have permission.
        """
        response = self.client.get(self.url)
        self.assertStatusOK(response)
        self.assertTemplateUsed(response, self.PERMISSION_DENIED_TEMPLATE)

    def test_load_page_as_source_outsider(self):
        """
        Load the page as a user outside the source ->
        sorry, don't have permission.
        """
        self.client.force_login(self.user_outsider)
        response = self.client.get(self.url)
        self.assertStatusOK(response)
        self.assertTemplateUsed(response, self.PERMISSION_DENIED_TEMPLATE)

    def test_load_page_as_source_viewer(self):
        """
        Load the page as a source viewer ->
        sorry, don't have permission.
        """
        self.client.force_login(self.user_viewer)
        response = self.client.get(self.url)
        self.assertStatusOK(response)
        self.assertTemplateUsed(response, self.PERMISSION_DENIED_TEMPLATE)

    def test_load_page(self):
        self.client.force_login(self.user_editor)
        response = self.client.get(self.url)
        self.assertStatusOK(response)
        self.assertTemplateUsed(
            response, 'annotations/annotation_history.html')

    def test_access_event(self):
        # Access the annotation tool
        self.client.force_login(self.user)
        self.client.get(reverse('annotation_tool', args=[self.img.pk]))

        # Check the history - as another user, so that other page elements
        # (such as the user profile link) don't throw off our count
        # of the annotator's username
        self.client.logout()
        self.client.force_login(self.user_editor)
        response = self.client.get(self.url)
        # Should have 1 table entry saying user_editor accessed.
        self.assertContains(response, "Accessed annotation tool", count=1)
        self.assertContains(response, self.user.username, count=1)

    def test_human_annotation_event(self):
        data = dict(
            label_1='A', label_2='', label_3='B',
            robot_1='false', robot_2='false', robot_3='false',
        )
        self.client.force_login(self.user)
        self.client.post(
            reverse('save_annotations_ajax', args=[self.img.pk]), data)

        # Check the history - as another user, so that other page elements
        # (such as the user profile link) don't throw off our count
        # of the annotator's username
        self.client.logout()
        self.client.force_login(self.user_editor)
        response = self.client.get(self.url)
        # Should have 1 table entry showing all the points that were changed.
        self.assertContains(response, "Point", count=2)
        self.assertContains(response, self.user.username, count=1)

    def test_human_annotation_overwrite(self):
        # Annotate as user: 2 new (2 history points)
        data = dict(
            label_1='A', label_2='', label_3='B',
            robot_1='false', robot_2='false', robot_3='false',
        )
        self.client.force_login(self.user)
        self.client.post(
            reverse('save_annotations_ajax', args=[self.img.pk]), data)

        # Annotate as user_editor: 1 replaced, 1 new, 1 same (2 history points)
        data = dict(
            label_1='B', label_2='A', label_3='B',
            robot_1='false', robot_2='false', robot_3='false',
        )
        self.client.logout()
        self.client.force_login(self.user_editor)
        self.client.post(
            reverse('save_annotations_ajax', args=[self.img.pk]), data)

        # Check the history - as another user, so that other page elements
        # (such as the user profile link) don't throw off our count
        # of the annotator's username
        self.client.logout()
        self.client.force_login(self.user_editor2)
        response = self.client.get(self.url)
        # The two history entries should have 4 instances of "Point"
        # combined: 2 in user's entry, 2 in user_editor's entry.
        self.assertContains(response, "Point", count=4)
        self.assertContains(response, self.user.username, count=1)
        self.assertContains(response, self.user_editor.username, count=1)

    def test_robot_annotation(self):
        robot = self.create_robot(self.source)
        self.add_robot_annotations(robot, self.img, {1: 'A', 2: 'B', 3: 'B'})

        self.client.force_login(self.user)
        response = self.client.get(self.url)
        # Should have 1 table entry showing all the points that were changed.
        self.assertContains(response, "Point", count=3)
        self.assertContains(response, "Robot {v}".format(v=robot.pk), count=1)


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

        if settings.UNIT_TEST_VERBOSITY >= 1:
            print "{pointgen_method}".format(
                pointgen_method=img.point_gen_method_display(),
            )
            print "{annotation_area}".format(
                annotation_area=img.annotation_area_display(),
            )
            print "Image dimensions: {width} x {height} pixels".format(
                width=img_width, height=img_height,
            )
            print (
                "X bounds: ({min_x}, {max_x})"
                " Y bounds: ({min_y}, {max_y})").format(
                    **area
                )

        for pt in points:
            self.assertTrue(area['min_x'] <= pt.column)
            self.assertTrue(pt.column <= area['max_x'])
            self.assertTrue(area['min_y'] <= pt.row)
            self.assertTrue(pt.row <= area['max_y'])

            if settings.UNIT_TEST_VERBOSITY >= 1:
                print "({col}, {row})".format(col=pt.column, row=pt.row)

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
