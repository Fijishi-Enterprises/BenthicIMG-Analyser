from django.core.urlresolvers import reverse

from annotations.models import Label
from images.model_utils import PointGen
from images.models import Source
from lib.test_utils import ClientTest


class PermissionTest(ClientTest):
    """
    Test page permissions.
    """
    @classmethod
    def setUpTestData(cls):
        super(PermissionTest, cls).setUpTestData()

        cls.user = cls.create_user()

        cls.source = cls.create_source(
            cls.user, visibility=Source.VisibilityTypes.PRIVATE,
            point_generation_type=PointGen.Types.SIMPLE,
            simple_number_of_points=10,
        )
        labels = cls.create_labels(cls.user, cls.source, ['A', 'B'], 'GroupA')
        cls.create_labelset(cls.user, cls.source, labels)

        cls.user_viewer = cls.create_user()
        cls.add_source_member(
            cls.user, cls.source, cls.user_viewer, Source.PermTypes.VIEW.code)
        cls.user_outsider = cls.create_user()

        cls.img1 = cls.upload_image_new(cls.user, cls.source)
        cls.add_annotations(cls.user, cls.img1, {1: 'A', 2: 'B'})

        cls.url = reverse('browse_patches', args=[cls.source.pk])

    def test_load_page_private_anonymous(self):
        """
        Load the private source's browse page while logged out ->
        sorry, don't have permission.
        """
        response = self.client.get(self.url)
        self.assertStatusOK(response)
        self.assertTemplateUsed(response, self.PERMISSION_DENIED_TEMPLATE)

    def test_load_page_private_as_source_outsider(self):
        """
        Load the page as a user outside the private source ->
        sorry, don't have permission.
        """
        self.client.force_login(self.user_outsider)
        response = self.client.get(self.url)
        self.assertStatusOK(response)
        self.assertTemplateUsed(response, self.PERMISSION_DENIED_TEMPLATE)

    def test_load_page_private_as_source_viewer(self):
        """
        Load the page as a source member with view permissions -> can load.
        """
        self.client.force_login(self.user_viewer)
        response = self.client.get(self.url)
        self.assertStatusOK(response)
        self.assertTemplateUsed(response, 'visualization/browse_patches.html')


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
            cls.user, cls.source, ['A', 'B'], 'GroupA')
        cls.create_labelset(cls.user, cls.source, labels)

        cls.user_editor = cls.create_user()
        cls.add_source_member(
            cls.user, cls.source, cls.user_editor, Source.PermTypes.EDIT.code)

        cls.img1 = cls.upload_image_new(cls.user, cls.source)
        cls.add_annotations(
            cls.user, cls.img1,
            {1: 'A', 2: 'A', 3: 'A', 4: 'A', 5: 'B', 6: 'B'})
        cls.add_annotations(
            cls.user_editor, cls.img1,
            {7: 'A', 8: 'A', 9: 'A', 10: 'B'})

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
        self.client.force_login(self.user)
        response = self.client.post(self.url, self.default_search_params)
        self.assertEqual(
            response.context['page_results'].paginator.count, 10)

    def test_filter_by_annotation_status(self):
        # TODO: Have a way to add robot annotations
        pass

    def test_filter_by_label(self):
        post_data = self.default_search_params.copy()
        post_data['label'] = Label.objects.get(code='A').pk

        self.client.force_login(self.user)
        response = self.client.post(self.url, post_data)
        self.assertEqual(
            response.context['page_results'].paginator.count, 7)

    def test_label_choices(self):
        self.client.force_login(self.user)
        response = self.client.get(self.url)

        search_form = response.context['patch_search_form']
        field = search_form.fields['label']
        self.assertListEqual(
            list(field.choices),
            [('', "All"),
             (Label.objects.get(code='A').pk, "A"),
             (Label.objects.get(code='B').pk, "B")]
        )

    def test_filter_by_annotator(self):
        post_data = self.default_search_params.copy()
        post_data['annotator'] = self.user.pk

        self.client.force_login(self.user)
        response = self.client.post(self.url, post_data)
        self.assertEqual(
            response.context['page_results'].paginator.count, 6)

    def test_annotator_choices(self):
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
        cls.img1 = cls.upload_image_new(cls.user, cls.source)
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
