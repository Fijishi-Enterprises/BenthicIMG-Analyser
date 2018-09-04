from __future__ import unicode_literals
import six

from bs4 import BeautifulSoup
from django.core.urlresolvers import reverse

from annotations.models import Annotation, AnnotationToolSettings
from images.model_utils import PointGen
from images.models import Source
from lib.test_utils import ClientTest


class PermissionTest(ClientTest):
    """
    Test page and Ajax-submit permissions.
    """
    @classmethod
    def setUpTestData(cls):
        super(PermissionTest, cls).setUpTestData()

        cls.user = cls.create_user()

        cls.source = cls.create_source(cls.user)
        labels = cls.create_labels(cls.user, ['A', 'B'], 'GroupA')
        cls.create_labelset(cls.user, cls.source, labels)

        cls.user_viewer = cls.create_user()
        cls.add_source_member(
            cls.user, cls.source, cls.user_viewer, Source.PermTypes.VIEW.code)
        cls.user_editor = cls.create_user()
        cls.add_source_member(
            cls.user, cls.source, cls.user_editor, Source.PermTypes.EDIT.code)

        cls.img = cls.upload_image(cls.user, cls.source)

    def test_load_page_anonymous(self):
        """
        Don't have permission.
        """
        url = reverse('annotation_tool', args=[self.img.pk])
        response = self.client.get(url)
        self.assertStatusOK(response)
        self.assertTemplateUsed(response, self.PERMISSION_DENIED_TEMPLATE)

    def test_load_page_as_source_viewer(self):
        """
        Don't have permission.
        """
        url = reverse('annotation_tool', args=[self.img.pk])
        self.client.force_login(self.user_viewer)
        response = self.client.get(url)
        self.assertStatusOK(response)
        self.assertTemplateUsed(response, self.PERMISSION_DENIED_TEMPLATE)

    def test_load_page_as_source_editor(self):
        """
        Can load.
        """
        url = reverse('annotation_tool', args=[self.img.pk])
        self.client.force_login(self.user_editor)
        response = self.client.get(url)
        self.assertStatusOK(response)
        self.assertTemplateUsed(response, 'annotations/annotation_tool.html')

    def test_save_annotations_anonymous(self):
        """
        Don't have permission.
        """
        url = reverse('save_annotations_ajax', args=[self.img.pk])
        response = self.client.post(url, dict()).json()
        # Response should include an error that contains the word "permission"
        self.assertTrue(
            'error' in response and "permission" in response['error'])

    def test_save_annotations_as_source_viewer(self):
        """
        Don't have permission.
        """
        url = reverse('save_annotations_ajax', args=[self.img.pk])
        self.client.force_login(self.user_viewer)
        response = self.client.post(url, dict()).json()
        # Response should include an error that contains the word "permission"
        self.assertTrue(
            'error' in response and "permission" in response['error'])

    def test_save_annotations_as_source_editor(self):
        """
        Can submit.
        """
        url = reverse('save_annotations_ajax', args=[self.img.pk])
        self.client.force_login(self.user_editor)
        response = self.client.post(url, dict()).json()
        # Response may include an error, but if it does, it shouldn't contain
        # the word "permission"
        self.assertFalse(
            'error' in response and "permission" in response['error'])

    def test_check_annotation_done_anonymous(self):
        """
        Don't have permission.
        """
        url = reverse('is_annotation_all_done_ajax', args=[self.img.pk])
        response = self.client.post(url, dict()).json()
        # Response should include an error that contains the word "permission"
        self.assertTrue(
            'error' in response and "permission" in response['error'])

    def test_check_annotation_done_as_source_viewer(self):
        """
        Can check.
        """
        url = reverse('is_annotation_all_done_ajax', args=[self.img.pk])
        self.client.force_login(self.user_viewer)
        response = self.client.post(url, dict()).json()
        # Response should include an error that contains the word "permission"
        self.assertFalse(
            'error' in response and "permission" in response['error'])

    def test_save_annotation_tool_settings_anonymous(self):
        """
        Must be logged in.
        """
        url = reverse('annotation_tool_settings_save')
        response = self.client.post(url, dict()).json()
        # Response should include an error that contains the words "signed in"
        self.assertTrue(
            'error' in response and "signed in" in response['error'])


class LoadImageTest(ClientTest):
    @classmethod
    def setUpTestData(cls):
        super(LoadImageTest, cls).setUpTestData()

        cls.user = cls.create_user()

        cls.source = cls.create_source(cls.user)
        labels = cls.create_labels(cls.user, ['A', 'B'], 'GroupA')
        cls.create_labelset(cls.user, cls.source, labels)

    def test_small_image(self):
        img = self.upload_image(
            self.user, self.source, dict(width=400, height=300))
        url = reverse('annotation_tool', args=[img.pk])

        self.client.force_login(self.user)
        response = self.client.get(url)
        self.assertStatusOK(response)
        self.assertTemplateUsed(response, 'annotations/annotation_tool.html')

        # Try fetching the page a second time, to make sure thumbnail
        # generation doesn't go nuts.
        response = self.client.get(url)
        self.assertStatusOK(response)

    def test_large_image(self):
        img = self.upload_image(
            self.user, self.source, dict(width=1600, height=1200))
        url = reverse('annotation_tool', args=[img.pk])

        self.client.force_login(self.user)
        response = self.client.get(url)
        self.assertStatusOK(response)
        self.assertTemplateUsed(response, 'annotations/annotation_tool.html')

        # Try fetching the page a second time, to make sure thumbnail
        # generation doesn't go nuts.
        response = self.client.get(url)
        self.assertStatusOK(response)


class NavigationTest(ClientTest):
    """
    Test the annotation tool buttons that let you navigate to other images.
    """
    @classmethod
    def setUpTestData(cls):
        super(NavigationTest, cls).setUpTestData()

        cls.user = cls.create_user()

        cls.source = cls.create_source(cls.user)
        labels = cls.create_labels(cls.user, ['A', 'B'], 'GroupA')
        cls.create_labelset(cls.user, cls.source, labels)

        cls.img1 = cls.upload_image(
            cls.user, cls.source, dict(filename='1.png'))
        cls.img2 = cls.upload_image(
            cls.user, cls.source, dict(filename='2.png'))
        cls.img3 = cls.upload_image(
            cls.user, cls.source, dict(filename='3.png'))

        cls.default_search_params = dict(
            image_form_type='search',
            aux1='', aux2='', aux3='', aux4='', aux5='',
            height_in_cm='', latitude='', longitude='', depth='',
            photographer='', framing='', balance='',
            date_filter_0='year', date_filter_1='',
            date_filter_2='', date_filter_3='',
            annotation_status='',
        )

    def test_next(self):
        self.client.force_login(self.user)
        response = self.client.get(
            reverse('annotation_tool', args=[self.img2.pk]))
        self.assertEqual(response.context['next_image'].pk, self.img3.pk)

    def test_prev(self):
        self.client.force_login(self.user)
        response = self.client.get(
            reverse('annotation_tool', args=[self.img2.pk]))
        self.assertEqual(response.context['prev_image'].pk, self.img1.pk)

    def test_next_wrap_to_first(self):
        self.client.force_login(self.user)
        response = self.client.get(
            reverse('annotation_tool', args=[self.img3.pk]))
        self.assertEqual(response.context['next_image'].pk, self.img1.pk)

    def test_prev_wrap_to_last(self):
        self.client.force_login(self.user)
        response = self.client.get(
            reverse('annotation_tool', args=[self.img1.pk]))
        self.assertEqual(response.context['prev_image'].pk, self.img3.pk)

    def test_next_with_search_filter(self):
        self.img1.metadata.aux1 = 'SiteA'
        self.img1.metadata.save()
        self.img2.metadata.aux1 = 'SiteB'
        self.img2.metadata.save()
        self.img3.metadata.aux1 = 'SiteA'
        self.img3.metadata.save()

        # Exclude img2 with the filter
        post_data = self.default_search_params.copy()
        post_data['aux1'] = 'SiteA'

        self.client.force_login(self.user)
        response = self.client.post(
            reverse('annotation_tool', args=[self.img1.pk]), post_data)
        self.assertEqual(response.context['next_image'].pk, self.img3.pk)

    def test_prev_with_image_id_filter(self):
        # Exclude img2 with the filter
        post_data = self.default_search_params.copy()
        post_data['image_form_type'] = 'ids'
        post_data['ids'] = ','.join([str(self.img1.pk), str(self.img3.pk)])

        self.client.force_login(self.user)
        response = self.client.post(
            reverse('annotation_tool', args=[self.img3.pk]), post_data)
        self.assertEqual(response.context['prev_image'].pk, self.img1.pk)


class SaveAnnotationsTest(ClientTest):
    @classmethod
    def setUpTestData(cls):
        super(SaveAnnotationsTest, cls).setUpTestData()

        cls.user = cls.create_user()

        cls.source = cls.create_source(
            cls.user, visibility=Source.VisibilityTypes.PUBLIC,
            point_generation_type=PointGen.Types.SIMPLE,
            simple_number_of_points=3,
        )
        labels = cls.create_labels(cls.user, ['A', 'B'], 'GroupA')
        cls.create_labelset(cls.user, cls.source, labels)

        cls.user_editor = cls.create_user()
        cls.add_source_member(
            cls.user, cls.source, cls.user_editor, Source.PermTypes.EDIT.code)

        cls.img = cls.upload_image(cls.user, cls.source)
        cls.url = reverse(
            'save_annotations_ajax', kwargs=dict(image_id=cls.img.pk))

    def test_save_annotations_some_points(self):
        """
        Save annotations for some points, but not all.
        """
        data = dict(
            label_1='A', label_2='', label_3='B',
            robot_1='false', robot_2='false', robot_3='false',
        )

        self.client.force_login(self.user)
        response = self.client.post(self.url, data).json()

        self.assertTrue('error' not in response)
        # Since we skipped some points, we shouldn't be 'all done'
        self.assertFalse(response['all_done'])

        # Check that point 2 doesn't have an annotation
        self.assertRaises(
            Annotation.DoesNotExist,
            Annotation.objects.get,
            image__pk=self.img.pk, point__point_number=2,
        )
        # Check that point 3's annotation is what we expect
        annotation_3 = Annotation.objects.get(
            image__pk=self.img.pk, point__point_number=3)
        self.assertEqual(annotation_3.label_code, 'B')

    def test_save_annotations_all_points(self):
        """
        Save annotations for all points.
        """
        data = dict(
            label_1='A', label_2='A', label_3='B',
            robot_1='false', robot_2='false', robot_3='false',
        )

        self.client.force_login(self.user)
        response = self.client.post(self.url, data).json()

        self.assertTrue('error' not in response)
        self.assertTrue(response['all_done'])

        # Check that point 2's annotation is what we expect
        annotation_2 = Annotation.objects.get(
            image__pk=self.img.pk, point__point_number=2)
        self.assertEqual(annotation_2.label_code, 'A')
        # Check that point 3's annotation is what we expect
        annotation_3 = Annotation.objects.get(
            image__pk=self.img.pk, point__point_number=3)
        self.assertEqual(annotation_3.label_code, 'B')

    def test_save_annotations_overwrite(self):
        """
        Save annotations on points that already have annotations.
        """
        data = dict(
            label_1='A', label_2='A', label_3='B',
            robot_1='false', robot_2='false', robot_3='false',
        )
        self.client.force_login(self.user)
        self.client.post(self.url, data)

        # Change one label, leave the rest the same
        data['label_2'] = 'B'
        # Send as a different user
        self.client.logout()
        self.client.force_login(self.user_editor)
        self.client.post(self.url, data)

        # Point 2's annotation: changed by the second user
        annotation_2 = Annotation.objects.get(
            image__pk=self.img.pk, point__point_number=2)
        self.assertEqual(annotation_2.label_code, 'B')
        self.assertEqual(annotation_2.user.username, self.user_editor.username)
        # Point 3's annotation: not changed by the second user
        annotation_3 = Annotation.objects.get(
            image__pk=self.img.pk, point__point_number=3)
        self.assertEqual(annotation_3.label_code, 'B')
        self.assertEqual(annotation_3.user.username, self.user.username)

    # TODO: Test loading the annotation form on the annotation tool page,
    # both with confirmed and unconfirmed annotations.


class IsAnnotationAllDoneTest(ClientTest):
    @classmethod
    def setUpTestData(cls):
        super(IsAnnotationAllDoneTest, cls).setUpTestData()

        cls.user = cls.create_user()

        cls.source = cls.create_source(
            cls.user, visibility=Source.VisibilityTypes.PUBLIC,
            point_generation_type=PointGen.Types.SIMPLE,
            simple_number_of_points=3,
        )
        labels = cls.create_labels(cls.user, ['A', 'B'], 'GroupA')
        cls.create_labelset(cls.user, cls.source, labels)

        cls.img = cls.upload_image(cls.user, cls.source)
        cls.url = reverse(
            'is_annotation_all_done_ajax', args=[cls.img.pk])

    def test_save_annotations_some_points(self):
        """
        Save annotations for some points, but not all.
        Then check all-done status.
        """
        annotations = {1: 'A', 2: 'B'}
        self.add_annotations(self.user, self.img, annotations)

        self.client.force_login(self.user)
        response = self.client.get(self.url).json()

        self.assertTrue('error' not in response)
        # Since we skipped some points, we shouldn't be 'all done'
        self.assertFalse(response['all_done'])

    def test_save_annotations_all_points(self):
        """
        Save annotations for all points.
        Then check all-done status.
        """
        annotations = {1: 'A', 2: 'B', 3: 'A'}
        self.add_annotations(self.user, self.img, annotations)

        self.client.force_login(self.user)
        response = self.client.get(self.url).json()

        self.assertTrue('error' not in response)
        # Since we labeled all points, we should be 'all done'
        self.assertTrue(response['all_done'])


class SettingsTest(ClientTest):
    """
    Test annotation tool settings.
    """
    @classmethod
    def setUpTestData(cls):
        super(SettingsTest, cls).setUpTestData()

        cls.user = cls.create_user()

        cls.source = cls.create_source(cls.user)
        labels = cls.create_labels(cls.user, ['A', 'B'], 'GroupA')
        cls.create_labelset(cls.user, cls.source, labels)

        cls.img = cls.upload_image(cls.user, cls.source)
        cls.tool_url = reverse('annotation_tool', args=[cls.img.pk])
        cls.settings_url = reverse('annotation_tool_settings_save')

        cls.field_names_to_types = dict(
            point_marker='choice',
            point_marker_size='integer',
            point_marker_is_scaled='boolean',
            point_number_size='integer',
            point_number_is_scaled='boolean',
            unannotated_point_color='color',
            robot_annotated_point_color='color',
            human_annotated_point_color='color',
            selected_point_color='color',
            show_machine_annotations='boolean',
        )

        cls.sample_settings = dict(
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

        cls.field_names_to_defaults = dict()
        for field_name in six.iterkeys(cls.field_names_to_types):
            field_meta = AnnotationToolSettings._meta.get_field(field_name)
            cls.field_names_to_defaults[field_name] = field_meta.default

    def get_field_value_from_soup(self, field_name, form_soup):
        field_type = self.field_names_to_types[field_name]

        if field_type == 'choice':
            field_soup = form_soup.find('select', dict(name=field_name))
            option_soup = field_soup.find('option', dict(selected='selected'))
            field_value = option_soup.attrs['value']
        elif field_type == 'integer':
            field_soup = form_soup.find('input', dict(name=field_name))
            field_value = int(field_soup.attrs['value'])
        elif field_type == 'color':
            field_soup = form_soup.find('input', dict(name=field_name))
            field_value = field_soup.attrs['value']
        elif field_type == 'boolean':
            field_soup = form_soup.find('input', dict(name=field_name))
            field_value = (field_soup.attrs.get('checked') == 'checked')
        else:
            raise ValueError("Not a recognized field type.")

        return field_value

    def test_tool_uses_defaults_if_never_saved_settings(self):
        self.client.force_login(self.user)
        response = self.client.get(self.tool_url)

        # Scrape the annotation tool's HTML to ensure the settings values are
        # as expected.
        response_soup = BeautifulSoup(response.content, 'html.parser')
        form_soup = response_soup.find(
            'form', dict(id='annotationToolSettingsForm'))

        for field_name, field_type in six.iteritems(self.field_names_to_types):
            field_value = self.get_field_value_from_soup(field_name, form_soup)
            field_meta = AnnotationToolSettings._meta.get_field(field_name)
            expected_value = field_meta.default
            self.assertEqual(field_value, expected_value)

    def test_tool_uses_saved_settings_when_present(self):
        self.client.force_login(self.user)
        response = self.client.get(self.tool_url)

        # Scrape the annotation tool's HTML to ensure the settings values are
        # as expected.
        response_soup = BeautifulSoup(response.content, 'html.parser')
        form_soup = response_soup.find(
            'form', dict(id='annotationToolSettingsForm'))

        for field_name, field_type in six.iteritems(self.field_names_to_types):
            field_value = self.get_field_value_from_soup(field_name, form_soup)
            field_meta = AnnotationToolSettings._meta.get_field(field_name)
            expected_value = field_meta.default
            self.assertEqual(field_value, expected_value)

    def test_save_settings_for_first_time(self):
        self.client.force_login(self.user)

        # Set settings.
        data = self.sample_settings
        response = self.client.post(self.settings_url, data).json()

        # Check response
        self.assertTrue('error' not in response)

        # Check settings in database
        settings = AnnotationToolSettings.objects.get(user=self.user)
        for field_name, setting in six.iteritems(self.sample_settings):
            self.assertEqual(getattr(settings, field_name), setting)

    def test_update_existing_settings(self):
        self.client.force_login(self.user)

        # Set settings.
        data = self.sample_settings
        self.client.post(self.settings_url, data).json()
        # Update settings.
        data = self.sample_settings.copy()
        data.update(point_marker='crosshair and circle')
        response = self.client.post(self.settings_url, data).json()

        # Check response
        self.assertTrue('error' not in response)

        # Check settings in database
        settings = AnnotationToolSettings.objects.get(user=self.user)
        for field_name, sample_setting in six.iteritems(self.sample_settings):
            if field_name == 'point_marker':
                self.assertEqual(
                    getattr(settings, field_name), 'crosshair and circle')
            else:
                self.assertEqual(getattr(settings, field_name), sample_setting)

    def test_missing_setting(self):
        self.client.force_login(self.user)

        data = self.sample_settings.copy()
        data.pop('point_marker')
        response = self.client.post(self.settings_url, data).json()

        self.assertTrue('error' in response)
        self.assertTrue(
            "Point marker: This field is required."
            in response['error'],
            msg=response['error'])

    def test_point_marker_not_recognized(self):
        self.client.force_login(self.user)

        data = self.sample_settings.copy()
        data['point_marker'] = 'Crosshair and box'
        response = self.client.post(self.settings_url, data).json()

        self.assertTrue('error' in response)
        self.assertTrue(
            "Point marker: Select a valid choice. Crosshair and box is not"
            " one of the available choices."
            in response['error'],
            msg=response['error'])

    def test_point_marker_size_not_an_integer(self):
        self.client.force_login(self.user)

        data = self.sample_settings.copy()
        data['point_marker_size'] = '15.5'
        response = self.client.post(self.settings_url, data).json()

        self.assertTrue('error' in response)
        self.assertTrue(
            "Point marker size: Enter a whole number."
            in response['error'],
            msg=response['error'])

    def test_point_marker_size_too_small(self):
        self.client.force_login(self.user)

        data = self.sample_settings.copy()
        data['point_marker_size'] = 0
        response = self.client.post(self.settings_url, data).json()

        self.assertTrue('error' in response)
        self.assertTrue(
            "Point marker size: Ensure this value is greater than or equal"
            " to 1."
            in response['error'],
            msg=response['error'])

    def test_point_marker_size_too_large(self):
        self.client.force_login(self.user)

        data = self.sample_settings.copy()
        data['point_marker_size'] = 31
        response = self.client.post(self.settings_url, data).json()

        self.assertTrue('error' in response)
        self.assertTrue(
            "Point marker size: Ensure this value is less than or equal to 30."
            in response['error'],
            msg=response['error'])

    def test_point_number_size_not_an_integer(self):
        self.client.force_login(self.user)

        data = self.sample_settings.copy()
        data['point_number_size'] = '0a'
        response = self.client.post(self.settings_url, data).json()

        self.assertTrue('error' in response)
        self.assertTrue(
            "Point number size: Enter a whole number."
            in response['error'],
            msg=response['error'])

    def test_point_number_size_too_small(self):
        self.client.force_login(self.user)

        data = self.sample_settings.copy()
        data['point_number_size'] = 0
        response = self.client.post(self.settings_url, data).json()

        self.assertTrue('error' in response)
        self.assertTrue(
            "Point number size: Ensure this value is greater than or equal"
            " to 1."
            in response['error'],
            msg=response['error'])

    def test_point_number_size_too_large(self):
        self.client.force_login(self.user)

        data = self.sample_settings.copy()
        data['point_number_size'] = 41
        response = self.client.post(self.settings_url, data).json()

        self.assertTrue('error' in response)
        self.assertTrue(
            "Point number size: Ensure this value is less than or equal to 40."
            in response['error'],
            msg=response['error'])

    # TODO: Implement color validation (6 digit uppercase hex string)
    # and test it here.
