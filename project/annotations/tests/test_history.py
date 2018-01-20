from __future__ import unicode_literals
from django.core.urlresolvers import reverse
from images.model_utils import PointGen
from images.models import Source
from lib.test_utils import ClientTest


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

    def view_history(self):
        return self.client.get(
            reverse('annotation_history', args=[self.img.pk]))

    def test_load_page_anonymous(self):
        """
        Load the page while logged out ->
        sorry, don't have permission.
        """
        response = self.view_history()
        self.assertStatusOK(response)
        self.assertTemplateUsed(response, self.PERMISSION_DENIED_TEMPLATE)

    def test_load_page_as_source_outsider(self):
        """
        Load the page as a user outside the source ->
        sorry, don't have permission.
        """
        self.client.force_login(self.user_outsider)
        response = self.view_history()
        self.assertStatusOK(response)
        self.assertTemplateUsed(response, self.PERMISSION_DENIED_TEMPLATE)

    def test_load_page_as_source_viewer(self):
        """
        Load the page as a source viewer ->
        sorry, don't have permission.
        """
        self.client.force_login(self.user_viewer)
        response = self.view_history()
        self.assertStatusOK(response)
        self.assertTemplateUsed(response, self.PERMISSION_DENIED_TEMPLATE)

    def test_load_page(self):
        self.client.force_login(self.user_editor)
        response = self.view_history()
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
        response = self.view_history()
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
        response = self.view_history()
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
        response = self.view_history()
        # The two history entries should have 4 instances of "Point"
        # combined: 2 in user's entry, 2 in user_editor's entry.
        self.assertContains(response, "Point", count=4)
        self.assertContains(response, self.user.username, count=1)
        self.assertContains(response, self.user_editor.username, count=1)

    def test_robot_annotation(self):
        robot = self.create_robot(self.source)
        self.add_robot_annotations(robot, self.img, {1: 'A', 2: 'B', 3: 'B'})

        self.client.force_login(self.user)
        response = self.view_history()
        # Should have 1 table entry showing all the points that were changed.
        self.assertContains(response, "Point", count=3)
        self.assertContains(response, "Robot {v}".format(v=robot.pk), count=1)
