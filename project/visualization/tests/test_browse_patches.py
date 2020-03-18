from __future__ import unicode_literals

from django.urls import reverse

from images.model_utils import PointGen
from images.models import Source
from lib.tests.utils import BasePermissionTest, ClientTest


class PermissionTest(BasePermissionTest):
    """
    Test page permissions.
    """
    def test_browse_patches(self):
        url = reverse('browse_patches', args=[self.source.pk])
        template = 'visualization/browse_patches.html'

        self.source_to_private()
        self.assertPermissionLevel(url, self.SOURCE_VIEW, template=template)
        self.source_to_public()
        self.assertPermissionLevel(url, self.SIGNED_OUT, template=template)


class SearchTest(ClientTest):

    @classmethod
    def setUpTestData(cls):
        super(SearchTest, cls).setUpTestData()

        cls.user = cls.create_user()

        cls.source = cls.create_source(
            cls.user,
            point_generation_type=PointGen.Types.SIMPLE,
            simple_number_of_points=10,
        )
        labels = cls.create_labels(
            cls.user, ['A', 'B'], 'GroupA')
        cls.create_labelset(cls.user, cls.source, labels)

        cls.user_editor = cls.create_user()
        cls.add_source_member(
            cls.user, cls.source, cls.user_editor, Source.PermTypes.EDIT.code)

        cls.img1 = cls.upload_image(cls.user, cls.source)

        cls.url = reverse('browse_patches', args=[cls.source.pk])

        cls.default_search_params = dict(
            image_form_type='search',
            aux1='', aux2='', aux3='', aux4='', aux5='',
            height_in_cm='', latitude='', longitude='', depth='',
            photographer='', framing='', balance='',
            date_filter_0='year', date_filter_1='',
            date_filter_2='', date_filter_3='',
            annotation_status='', label='', annotator='',
        )

    def test_page_landing(self):
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        self.assertContains(
            response,
            "Use the form to retrieve image patches"
            " corresponding to annotated points."
        )

    def test_default_search(self):
        self.add_annotations(
            self.user, self.img1,
            {1: 'A', 2: 'A', 3: 'A'})

        self.client.force_login(self.user)
        response = self.client.post(self.url, self.default_search_params)
        self.assertEqual(
            response.context['page_results'].paginator.count, 3)

    def test_filter_by_annotation_status_confirmed(self):
        robot = self.create_robot(self.source)
        # 10 points per image
        self.add_robot_annotations(robot, self.img1)
        self.add_annotations(
            self.user, self.img1,
            {1: 'A', 2: 'A', 3: 'A'})

        post_data = self.default_search_params.copy()
        post_data['annotation_status'] = 'confirmed'

        self.client.force_login(self.user)
        response = self.client.post(self.url, post_data)
        self.assertEqual(
            response.context['page_results'].paginator.count, 3)

    def test_filter_by_annotation_status_unconfirmed(self):
        robot = self.create_robot(self.source)
        # 10 points per image
        self.add_robot_annotations(robot, self.img1)
        self.add_annotations(
            self.user, self.img1,
            {1: 'A', 2: 'A', 3: 'A'})

        post_data = self.default_search_params.copy()
        post_data['annotation_status'] = 'unconfirmed'

        self.client.force_login(self.user)
        response = self.client.post(self.url, post_data)
        self.assertEqual(
            response.context['page_results'].paginator.count, 7)

    def test_filter_by_label(self):
        self.add_annotations(
            self.user, self.img1,
            {1: 'A', 2: 'A', 3: 'A', 4: 'B', 5: 'B'})

        post_data = self.default_search_params.copy()
        post_data['label'] = self.source.labelset.get_global_by_code('A').pk

        self.client.force_login(self.user)
        response = self.client.post(self.url, post_data)
        self.assertEqual(
            response.context['page_results'].paginator.count, 3)

    def test_label_choices(self):
        self.add_annotations(
            self.user, self.img1,
            {1: 'A', 2: 'A', 3: 'A', 4: 'B', 5: 'B'})

        self.client.force_login(self.user)
        response = self.client.get(self.url)

        search_form = response.context['patch_search_form']
        field = search_form.fields['label']
        self.assertListEqual(
            list(field.choices),
            [('', "All"),
             (self.source.labelset.get_global_by_code('A').pk, "A"),
             (self.source.labelset.get_global_by_code('B').pk, "B")]
        )

    def test_filter_by_annotator(self):
        self.add_annotations(
            self.user, self.img1,
            {1: 'A', 2: 'A', 3: 'A'})
        self.add_annotations(
            self.user_editor, self.img1,
            {4: 'A', 5: 'A'})

        post_data = self.default_search_params.copy()
        post_data['annotator'] = self.user.pk

        self.client.force_login(self.user)
        response = self.client.post(self.url, post_data)
        self.assertEqual(
            response.context['page_results'].paginator.count, 3)

    def test_annotator_choices(self):
        self.add_annotations(
            self.user, self.img1,
            {1: 'A', 2: 'A', 3: 'A'})
        self.add_annotations(
            self.user_editor, self.img1,
            {4: 'A', 5: 'A'})

        self.client.force_login(self.user)
        response = self.client.get(self.url)

        search_form = response.context['patch_search_form']
        field = search_form.fields['annotator']
        self.assertListEqual(
            list(field.choices),
            [('', "All"), (self.user.pk, self.user.username),
             (self.user_editor.pk, self.user_editor.username)]
        )


class NoLabelsetTest(ClientTest):

    @classmethod
    def setUpTestData(cls):
        super(NoLabelsetTest, cls).setUpTestData()

        cls.user = cls.create_user()
        cls.source = cls.create_source(cls.user)
        cls.img1 = cls.upload_image(cls.user, cls.source)
        cls.url = reverse('browse_patches', args=[cls.source.pk])

        cls.default_search_params = dict(
            image_form_type='search',
            aux1='', aux2='', aux3='', aux4='', aux5='',
            height_in_cm='', latitude='', longitude='', depth='',
            photographer='', framing='', balance='',
            date_filter_0='year', date_filter_1='',
            date_filter_2='', date_filter_3='',
            annotation_status='', label='', annotator='',
        )

    def test_default_search(self):
        """
        No labelset shouldn't be an error case.
        It just won't return anything exciting.
        """
        self.client.force_login(self.user)
        response = self.client.post(self.url, self.default_search_params)
        self.assertContains(response, "No patch results.")
