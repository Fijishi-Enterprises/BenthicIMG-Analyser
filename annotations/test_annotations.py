import json
import random
from django.conf import settings
from django.contrib.auth.models import User
from django.core.urlresolvers import reverse
from annotations.model_utils import AnnotationAreaUtils
from annotations.models import Label, Annotation, AnnotationToolSettings
from images.model_utils import PointGen
from images.models import Source, Image, Point
from lib.test_utils import ClientTest, MediaTestComponent


class AnnotationToolTest(ClientTest):
    """
    Test the annotation tool page.
    """
    extra_components = [MediaTestComponent]
    fixtures = ['test_users.yaml', 'test_labels.yaml',
                'test_labelsets.yaml', 'test_sources_with_labelsets.yaml']
    source_member_roles = [
        ('Labelset 1key', 'user2', Source.PermTypes.EDIT.code),
    ]

    def setUp(self):
        super(AnnotationToolTest, self).setUp()
        self.source_id = Source.objects.get(name='Labelset 1key').pk

    def test_load_page_anonymous(self):
        """
        Load the page while logged out ->
        sorry, don't have permission.
        """
        self.client.login(username='user2', password='secret')
        image_id = self.upload_image('001_2012-05-01_color-grid-001.png')[0]
        self.client.logout()

        url = reverse('annotation_tool', kwargs=dict(image_id=image_id))

        response = self.client.get(url)
        self.assertStatusOK(response)
        self.assertTemplateUsed(response, self.PERMISSION_DENIED_TEMPLATE)

    def test_load_page_as_source_outsider(self):
        """
        Load the page as a user outside the source ->
        sorry, don't have permission.
        """
        self.client.login(username='user2', password='secret')
        image_id = self.upload_image('001_2012-05-01_color-grid-001.png')[0]
        self.client.logout()

        self.client.login(username='user3', password='secret')
        url = reverse('annotation_tool', kwargs=dict(image_id=image_id))

        response = self.client.get(url)
        self.assertStatusOK(response)
        self.assertTemplateUsed(response, self.PERMISSION_DENIED_TEMPLATE)

    def test_annotation_tool_with_small_image(self):
        self.client.login(username='user2', password='secret')
        image_id = self.upload_image('001_2012-05-01_color-grid-001.png')[0]
        url = reverse('annotation_tool', kwargs=dict(image_id=image_id))

        response = self.client.get(url)
        self.assertStatusOK(response)
        self.assertTemplateUsed(response, 'annotations/annotation_tool.html')

        # Try fetching the page a second time, to make sure thumbnail
        # generation doesn't go nuts.
        response = self.client.get(url)
        self.assertStatusOK(response)

        # TODO: Add more checks.

    def test_annotation_tool_with_large_image(self):
        self.client.login(username='user2', password='secret')
        image_id = self.upload_image('002_2012-05-29_color-grid-001_large.png')[0]
        url = reverse('annotation_tool', kwargs=dict(image_id=image_id))

        response = self.client.get(url)
        self.assertStatusOK(response)

        # Try fetching the page a second time, to make sure thumbnail
        # generation doesn't go nuts.
        response = self.client.get(url)
        self.assertStatusOK(response)


class SaveAnnotationsTest(ClientTest):
    """
    Test saving annotations via the Ajax view.
    """
    extra_components = [MediaTestComponent]
    fixtures = ['test_users.yaml', 'test_labels.yaml',
                'test_labelsets.yaml', 'test_sources_with_labelsets.yaml']
    source_member_roles = [
        ('Labelset 1key', 'user2', Source.PermTypes.EDIT.code),
    ]

    def setUp(self):
        super(SaveAnnotationsTest, self).setUp()
        self.source_id = Source.objects.get(name='Labelset 1key').pk

        # Upload an image
        self.client.login(username='user2', password='secret')
        self.image_id = self.upload_image('001_2012-05-01_color-grid-001.png')[0]
        self.client.logout()

    def test_load_page_anonymous(self):
        """
        Load the page while logged out ->
        sorry, don't have permission.
        """
        url = reverse(
            'save_annotations_ajax', kwargs=dict(image_id=self.image_id))

        data = dict()

        response = self.client.post(url, data)
        response_json = response.json()
        # Response should include an error that contains the word "permission"
        self.assertTrue('error' in response_json)
        self.assertTrue("permission" in response_json['error'])

    def test_load_page_as_source_outsider(self):
        """
        Load the page as a user outside the source ->
        sorry, don't have permission.
        """
        self.client.login(username='user3', password='secret')
        url = reverse(
            'save_annotations_ajax', kwargs=dict(image_id=self.image_id))

        data = dict()

        response = self.client.post(url, data)
        response_json = response.json()

        # Response should include an error that contains the word "permission"
        self.assertTrue('error' in response_json)
        self.assertTrue("permission" in response_json['error'])

    def test_save_annotations_some_points(self):
        """
        Save annotations for some points, but not all.
        """
        self.client.login(username='user2', password='secret')
        url = reverse(
            'save_annotations_ajax', kwargs=dict(image_id=self.image_id))

        data = dict()
        image = Image.objects.get(pk=self.image_id)

        labels = Label.objects.filter(labelset=image.source.labelset)
        label_codes = labels.values_list('code', flat=True)
        num_points = Point.objects.filter(image=image).count()

        # Assign annotations for points
        for point_num in range(1, num_points+1):
            if point_num % 5 == 2:
                # Skip point 2, 7, 12, etc.
                data['label_'+str(point_num)] = ''
            else:
                # Assign a random label
                data['label_'+str(point_num)] = random.choice(label_codes)
            data['robot_'+str(point_num)] = json.dumps(False)

        response = self.client.post(url, data)
        response_json = response.json()

        self.assertTrue('error' not in response_json)
        # Since we skipped some points, we shouldn't be 'all done'
        self.assertTrue('all_done' not in response_json)

        # Check that point 2 doesn't have an annotation
        self.assertRaises(
            Annotation.DoesNotExist,
            Annotation.objects.get,
            image__pk=self.image_id, point__point_number=2,
        )
        # Check that point 3's annotation is what we expect
        annotation_3 = Annotation.objects.get(
            image__pk=self.image_id, point__point_number=3)
        self.assertEqual(annotation_3.label.code, data['label_3'])

    def test_save_annotations_all_points(self):
        """
        Save annotations for all points.
        """
        self.client.login(username='user2', password='secret')
        url = reverse(
            'save_annotations_ajax', kwargs=dict(image_id=self.image_id))

        data = dict()
        image = Image.objects.get(pk=self.image_id)

        labels = Label.objects.filter(labelset=image.source.labelset)
        label_codes = labels.values_list('code', flat=True)
        num_points = Point.objects.filter(image=image).count()

        # Assign annotations for points
        for point_num in range(1, num_points+1):
            # Assign a random label
            data['label_'+str(point_num)] = random.choice(label_codes)
            data['robot_'+str(point_num)] = json.dumps(False)

        response = self.client.post(url, data)
        response_json = response.json()

        self.assertTrue('error' not in response_json)
        self.assertTrue('all_done' in response_json)

        # Check that point 2's annotation is what we expect
        annotation_2 = Annotation.objects.get(
            image__pk=self.image_id, point__point_number=2)
        self.assertEqual(annotation_2.label.code, data['label_2'])
        # Check that point 3's annotation is what we expect
        annotation_3 = Annotation.objects.get(
            image__pk=self.image_id, point__point_number=3)
        self.assertEqual(annotation_3.label.code, data['label_3'])

    def test_save_annotations_overwrite(self):
        """
        Save annotations on points that already have annotations.
        """
        self.client.login(username='user2', password='secret')
        url = reverse(
            'save_annotations_ajax', kwargs=dict(image_id=self.image_id))

        data = dict()
        image = Image.objects.get(pk=self.image_id)

        labels = Label.objects.filter(labelset=image.source.labelset)
        label_codes = labels.values_list('code', flat=True)
        num_points = Point.objects.filter(image=image).count()

        # Assign annotations for points
        for point_num in range(1, num_points+1):
            if point_num == 2:
                data['label_'+str(point_num)] = label_codes[0]
            else:
                # Assign a random label
                data['label_'+str(point_num)] = random.choice(label_codes)
            data['robot_'+str(point_num)] = json.dumps(False)
        self.client.post(url, data)

        # Now save one annotation as superuser_user.
        self.client.logout()
        self.client.login(username='superuser_user', password='secret')
        # Change one label, leave the rest the same
        data['label_2'] = label_codes[1]
        # Send again
        self.client.post(url, data)

        # Point 2's annotation: changed by superuser_user
        annotation_2 = Annotation.objects.get(
            image__pk=self.image_id, point__point_number=2)
        self.assertEqual(annotation_2.label.code, label_codes[1])
        self.assertEqual(annotation_2.user.username, 'superuser_user')
        # Point 3's annotation: not changed by superuser_user
        annotation_3 = Annotation.objects.get(
            image__pk=self.image_id, point__point_number=3)
        self.assertEqual(annotation_3.label.code, data['label_3'])
        self.assertEqual(annotation_3.user.username, 'user2')


class IsAnnotationAllDoneTest(ClientTest):
    """
    Test the Ajax view that reports if an image's annotations are all done.
    """
    extra_components = [MediaTestComponent]
    fixtures = ['test_users.yaml', 'test_labels.yaml',
                'test_labelsets.yaml', 'test_sources_with_labelsets.yaml']
    source_member_roles = [
        ('Labelset 1key', 'user2', Source.PermTypes.EDIT.code),
    ]

    def setUp(self):
        super(IsAnnotationAllDoneTest, self).setUp()
        self.source_id = Source.objects.get(name='Labelset 1key').pk

        # Upload an image
        self.client.login(username='user2', password='secret')
        self.image_id = self.upload_image('001_2012-05-01_color-grid-001.png')[0]
        self.client.logout()

    def test_load_page_anonymous(self):
        """
        Load the page while logged out ->
        sorry, don't have permission.
        """
        url = reverse(
            'is_annotation_all_done_ajax', kwargs=dict(image_id=self.image_id))

        data = dict()

        response = self.client.post(url, data)
        response_json = response.json()
        # Response should include an error that contains the word "permission"
        self.assertTrue('error' in response_json)
        self.assertTrue("permission" in response_json['error'])

    def test_load_page_as_source_outsider(self):
        """
        Load the page as a user outside the source ->
        sorry, don't have permission.
        """
        self.client.login(username='user3', password='secret')
        url = reverse(
            'is_annotation_all_done_ajax', kwargs=dict(image_id=self.image_id))

        data = dict()

        response = self.client.post(url, data)
        response_json = response.json()

        # Response should include an error that contains the word "permission"
        self.assertTrue('error' in response_json)
        self.assertTrue("permission" in response_json['error'])

    def test_save_annotations_some_points(self):
        """
        Save annotations for some points, but not all.
        Then check all-done status.
        """
        self.client.login(username='user2', password='secret')
        url = reverse(
            'save_annotations_ajax', kwargs=dict(image_id=self.image_id))

        data = dict()
        image = Image.objects.get(pk=self.image_id)

        labels = Label.objects.filter(labelset=image.source.labelset)
        label_codes = labels.values_list('code', flat=True)
        num_points = Point.objects.filter(image=image).count()

        # Assign annotations for points
        for point_num in range(1, num_points+1):
            if point_num % 5 == 2:
                # Skip point 2, 7, 12, etc.
                data['label_'+str(point_num)] = ''
            else:
                # Assign a random label
                data['label_'+str(point_num)] = random.choice(label_codes)
            data['robot_'+str(point_num)] = json.dumps(False)

        self.client.post(url, data)

        # Check all-done status
        url = reverse(
            'is_annotation_all_done_ajax', kwargs=dict(image_id=self.image_id))
        response = self.client.post(url, data)
        response_json = response.json()

        self.assertTrue('error' not in response_json)
        # Since we skipped some points, we shouldn't be 'all done'
        self.assertFalse(response_json['all_done'])

    def test_save_annotations_all_points(self):
        """
        Save annotations for all points.
        Then check all-done status.
        """
        self.client.login(username='user2', password='secret')
        url = reverse(
            'save_annotations_ajax', kwargs=dict(image_id=self.image_id))

        data = dict()
        image = Image.objects.get(pk=self.image_id)

        labels = Label.objects.filter(labelset=image.source.labelset)
        label_codes = labels.values_list('code', flat=True)
        num_points = Point.objects.filter(image=image).count()

        # Assign annotations for points
        for point_num in range(1, num_points+1):
            # Assign a random label
            data['label_'+str(point_num)] = random.choice(label_codes)
            data['robot_'+str(point_num)] = json.dumps(False)

        self.client.post(url, data)

        # Check all-done status
        url = reverse(
            'is_annotation_all_done_ajax', kwargs=dict(image_id=self.image_id))
        response = self.client.post(url, data)
        response_json = response.json()

        self.assertTrue('error' not in response_json)
        # Since we labeled all points, we should be 'all done'
        self.assertTrue(response_json['all_done'])


class AnnotationToolSettingsSaveTest(ClientTest):
    """
    Test the Ajax view that saves a user's annotation tool settings.
    """
    extra_components = [MediaTestComponent]
    fixtures = ['test_users.yaml', 'test_labels.yaml',
                'test_labelsets.yaml', 'test_sources_with_labelsets.yaml']
    source_member_roles = [
        ('Labelset 1key', 'user2', Source.PermTypes.EDIT.code),
    ]

    def test_load_view_anonymous(self):
        """
        Load view while not logged in -> error response.
        """
        url = reverse('annotation_tool_settings_save')
        response = self.client.post(url)

        # Check response
        response_json = response.json()
        self.assertTrue('error' in response_json)
        self.assertTrue("logged in" in response_json['error'])

    def test_save_settings(self):
        """
        Save settings.
        """
        self.client.login(username='user2', password='secret')

        # First ensure that this user has a settings object in the DB.
        AnnotationToolSettings.objects.create(
            user=User.objects.get(username='user2'))

        # Set settings
        url = reverse('annotation_tool_settings_save')
        data = dict(
            point_marker='box',
            point_marker_size=19,
            point_marker_is_scaled=True,
            point_number_size=9,
            point_number_is_scaled=True,
            unannotated_point_color='FF0000',
            robot_annotated_point_color='ABCDEF',
            human_annotated_point_color='012345',
            selected_point_color='FFBBBB',
            show_machine_annotations=False,
        )
        response = self.client.post(url, data)

        # Check response
        response_json = response.json()
        self.assertTrue('error' not in response_json)

        # Check settings
        settings = AnnotationToolSettings.objects.get(user__username='user2')
        self.assertEqual(settings.point_marker, 'box')
        self.assertEqual(settings.point_marker_size, 19)
        self.assertEqual(settings.point_marker_is_scaled, True)
        self.assertEqual(settings.point_number_size, 9)
        self.assertEqual(settings.point_number_is_scaled, True)
        self.assertEqual(settings.unannotated_point_color, 'FF0000')
        self.assertEqual(settings.robot_annotated_point_color, 'ABCDEF')
        self.assertEqual(settings.human_annotated_point_color, '012345')
        self.assertEqual(settings.selected_point_color, 'FFBBBB')
        self.assertEqual(settings.show_machine_annotations, False)


class AnnotationAreaEditTest(ClientTest):
    """
    Test the annotation area edit page.
    """
    extra_components = [MediaTestComponent]
    fixtures = ['test_users.yaml', 'test_labels.yaml',
                'test_labelsets.yaml', 'test_sources_with_labelsets.yaml']
    source_member_roles = [
        ('Labelset 1key', 'user2', Source.PermTypes.EDIT.code),
    ]

    def setUp(self):
        super(AnnotationAreaEditTest, self).setUp()
        self.source_id = Source.objects.get(name='Labelset 1key').pk

    def test_load_page_anonymous(self):
        """
        Load the page while logged out ->
        sorry, don't have permission.
        """
        self.client.login(username='user2', password='secret')
        image_id = self.upload_image('001_2012-05-01_color-grid-001.png')[0]
        self.client.logout()

        url = reverse('annotation_area_edit', kwargs=dict(image_id=image_id))

        response = self.client.get(url)
        self.assertStatusOK(response)
        self.assertTemplateUsed(response, self.PERMISSION_DENIED_TEMPLATE)

    def test_load_page_as_source_outsider(self):
        """
        Load the page as a user outside the source ->
        sorry, don't have permission.
        """
        self.client.login(username='user2', password='secret')
        image_id = self.upload_image('001_2012-05-01_color-grid-001.png')[0]
        self.client.logout()

        self.client.login(username='user3', password='secret')
        url = reverse('annotation_area_edit', kwargs=dict(image_id=image_id))

        response = self.client.get(url)
        self.assertStatusOK(response)
        self.assertTemplateUsed(response, self.PERMISSION_DENIED_TEMPLATE)

    def test_load_page(self):
        self.client.login(username='user2', password='secret')
        image_id = self.upload_image('001_2012-05-01_color-grid-001.png')[0]
        url = reverse('annotation_area_edit', kwargs=dict(image_id=image_id))

        response = self.client.get(url)
        self.assertStatusOK(response)
        self.assertTemplateUsed(response, 'annotations/annotation_area_edit.html')

    # TODO: Test submitting a new annotation area


class AnnotationHistoryTest(ClientTest):
    """
    Test the annotation history page.
    """
    extra_components = [MediaTestComponent]
    fixtures = ['test_users.yaml', 'test_labels.yaml',
                'test_labelsets.yaml', 'test_sources_with_labelsets.yaml']
    source_member_roles = [
        ('Labelset 1key', 'user2', Source.PermTypes.EDIT.code),
        ]

    def setUp(self):
        super(AnnotationHistoryTest, self).setUp()
        self.source_id = Source.objects.get(name='Labelset 1key').pk

        # Upload an image
        self.client.login(username='user2', password='secret')
        self.image_id = self.upload_image('001_2012-05-01_color-grid-001.png')[0]
        self.client.logout()

    def test_load_page_anonymous(self):
        """
        Load the page while logged out ->
        sorry, don't have permission.
        """

        url = reverse('annotation_history', kwargs=dict(image_id=self.image_id))

        response = self.client.get(url)
        self.assertStatusOK(response)
        self.assertTemplateUsed(response, self.PERMISSION_DENIED_TEMPLATE)

    def test_load_page_as_source_outsider(self):
        """
        Load the page as a user outside the source ->
        sorry, don't have permission.
        """
        self.client.login(username='user3', password='secret')
        url = reverse('annotation_history', kwargs=dict(image_id=self.image_id))

        response = self.client.get(url)
        self.assertStatusOK(response)
        self.assertTemplateUsed(response, self.PERMISSION_DENIED_TEMPLATE)

    def test_load_page(self):
        self.client.login(username='user2', password='secret')
        url = reverse('annotation_history', kwargs=dict(image_id=self.image_id))

        response = self.client.get(url)
        self.assertStatusOK(response)
        self.assertTemplateUsed(response, 'annotations/annotation_history.html')

    def test_access_event(self):
        self.client.login(username='user2', password='secret')

        # Access the annotation tool
        url = reverse('annotation_tool', kwargs=dict(image_id=self.image_id))
        self.client.get(url)

        # Check the history - as another user, so we can count the instances
        # of the annotating user
        self.client.logout()
        self.client.login(username='superuser_user', password='secret')
        url = reverse('annotation_history', kwargs=dict(image_id=self.image_id))
        response = self.client.get(url)
        # Should have 1 table entry saying user2 accessed.
        self.assertContains(response, "Accessed annotation tool", count=1)
        self.assertContains(response, "user2", count=1)

    def test_annotation_event(self):
        self.client.login(username='user2', password='secret')

        # Save annotations
        url = reverse(
            'save_annotations_ajax', kwargs=dict(image_id=self.image_id))

        data = dict()
        image = Image.objects.get(pk=self.image_id)
        labels = Label.objects.filter(labelset=image.source.labelset)
        label_codes = labels.values_list('code', flat=True)
        num_points = Point.objects.filter(image=image).count()

        for point_num in range(1, num_points+1):
            # Assign a random label
            data['label_'+str(point_num)] = random.choice(label_codes)
            data['robot_'+str(point_num)] = json.dumps(False)
        self.client.post(url, data)

        # Check the history - as another user, so we can count the instances
        # of the annotating user
        self.client.logout()
        self.client.login(username='superuser_user', password='secret')
        url = reverse('annotation_history', kwargs=dict(image_id=self.image_id))
        response = self.client.get(url)
        # Should have 1 table entry showing all the points that were changed.
        self.assertContains(response, "Point", count=num_points)
        self.assertContains(response, "user2", count=1)

    def test_annotation_overwrite(self):
        self.client.login(username='user2', password='secret')

        # Save annotations as user2
        url = reverse(
            'save_annotations_ajax', kwargs=dict(image_id=self.image_id))

        data = dict()
        image = Image.objects.get(pk=self.image_id)
        labels = Label.objects.filter(labelset=image.source.labelset)
        label_codes = labels.values_list('code', flat=True)
        num_points = Point.objects.filter(image=image).count()

        for point_num in range(1, num_points+1):
            if 1 <= point_num and point_num <= 2:
                # Assign a fixed label for points 1 and 2
                data['label_'+str(point_num)] = label_codes[1]
            else:
                # Assign a random label
                data['label_'+str(point_num)] = random.choice(label_codes)
            data['robot_'+str(point_num)] = json.dumps(False)
        self.client.post(url, data)

        # Save annotations as superuser_user, changing just 2 labels
        self.client.logout()
        self.client.login(username='superuser_user', password='secret')
        data['label_1'] = label_codes[0]
        data['label_2'] = label_codes[0]
        self.client.post(url, data)

        # Check the history - as user2, so we can count the instances
        # of superuser_user
        self.client.logout()
        self.client.login(username='user2', password='secret')
        url = reverse('annotation_history', kwargs=dict(image_id=self.image_id))
        response = self.client.get(url)
        # superuser_user should be on the second history entry.
        # The two history entries should have num_points+2 instances of "Point"
        # combined: num_points in user2's entry, 2 in superuser_user's entry.
        self.assertContains(response, "Point", count=num_points+2)
        self.assertContains(response, "superuser_user", count=1)


class PointGenTest(ClientTest):
    """
    Test generation of annotation points.
    """
    extra_components = [MediaTestComponent]
    fixtures = [
        'test_users.yaml',
        'test_sources_with_different_pointgen_params.yaml'
    ]
    source_member_roles = [
        ('Pointgen simple 1', 'user2', Source.PermTypes.ADMIN.code),
        ('Pointgen simple 2', 'user2', Source.PermTypes.ADMIN.code),
    ]

    def setUp(self):
        super(PointGenTest, self).setUp()
        self.client.login(username='user2', password='secret')

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
        self.assertEqual(points.count(), pointgen_args['simple_number_of_points'])

        # Find the expected annotation area, expressed in pixels.
        d = AnnotationAreaUtils.db_format_to_numbers(img.metadata.annotation_area)
        annoarea_type = d.pop('type')
        if annoarea_type == AnnotationAreaUtils.TYPE_PERCENTAGES:
            area = AnnotationAreaUtils.percentages_to_pixels(width=img_width, height=img_height, **d)
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
            print "X bounds: ({min_x}, {max_x}) Y bounds: ({min_y}, {max_y})".format(
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

        Test two different sources (with different pointgen parameters) and
        two different images (of different width/height) for each source.
        """
        image_ids = []

        self.source_id = Source.objects.get(name='Pointgen simple 1').id

        image_ids.append(self.upload_image('001_2012-10-14_small-rect.png')[0])
        image_ids.append(self.upload_image('002_2012-10-14_tiny-rect.png')[0])

        self.source_id = Source.objects.get(name='Pointgen simple 2').id

        image_ids.append(self.upload_image('001_2012-10-14_small-rect.png')[0])
        image_ids.append(self.upload_image('002_2012-10-14_tiny-rect.png')[0])

        for image_id in image_ids:
            self.pointgen_check(image_id)

    # TODO: Test stratified random and uniform grid as well, not just simple random.
    # TODO: Test unusual annotation areas: min and max very close or the same, and decimal percentages.