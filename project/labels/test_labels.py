from django.core.urlresolvers import reverse

from images.model_utils import PointGen
from images.models import Source
from labels.models import LabelGroup, Label
from lib.test_utils import ClientTest, sample_image_as_file


class LabelListTest(ClientTest):
    """
    Test the label list page.
    """
    @classmethod
    def setUpTestData(cls):
        # Call the parent's setup (while still using this class as cls)
        super(LabelListTest, cls).setUpTestData()

        cls.user = cls.create_user()

        # Create labels
        cls.labels = cls.create_labels(
            cls.user, ['A', 'B'], "Group1")

    def test_load_page(self):
        """Load the page."""
        response = self.client.get(reverse('label_list'))
        self.assertStatusOK(response)


class LabelSearchTest(ClientTest):
    """
    Test the label search Ajax view.
    """
    @classmethod
    def setUpTestData(cls):
        # Call the parent's setup (while still using this class as cls)
        super(LabelSearchTest, cls).setUpTestData()

        cls.user = cls.create_user()
        cls.url = reverse('label_search_ajax')

    def assertLabels(self, response, label_names):
        for name in label_names:
            self.assertContains(
                response,
                '<div class="label-add-box" data-label-id="{pk}">'.format(
                    pk=Label.objects.get(name=name).pk))
        self.assertContains(
            response, 'div class="label-add-box"', count=len(label_names))

    def test_match_full_name(self):
        self.create_labels(self.user, ["Red", "Blue"], "Group1")

        self.client.force_login(self.user)
        response = self.client.get(self.url, dict(search="Red"))
        self.assertLabels(response, ["Red"])

    def test_match_part_of_name(self):
        self.create_labels(self.user, ["Red", "Blue"], "Group1")

        self.client.force_login(self.user)
        response = self.client.get(self.url, dict(search="Blu"))
        self.assertLabels(response, ["Blue"])

    def test_match_case_insensitive(self):
        self.create_labels(self.user, ["Red", "Blue"], "Group1")

        self.client.force_login(self.user)
        response = self.client.get(self.url, dict(search="BLUE"))
        self.assertLabels(response, ["Blue"])

    def test_match_multiple_labels(self):
        self.create_labels(
            self.user, ["Red", "Light Blue", "Dark Blue"], "Group1")

        self.client.force_login(self.user)
        response = self.client.get(self.url, dict(search="Blue"))
        self.assertLabels(response, ["Light Blue", "Dark Blue"])

    def test_multiple_words(self):
        self.create_labels(
            self.user, ["Light Blue", "Dark Blue", "Dark Red"], "Group1")

        self.client.force_login(self.user)
        response = self.client.get(self.url, dict(search="Dark Blue"))
        self.assertLabels(response, ["Dark Blue"])

    def test_no_match(self):
        self.create_labels(self.user, ["Red", "Blue"], "Group1")

        self.client.force_login(self.user)
        response = self.client.get(self.url, dict(search="Green"))
        self.assertLabels(response, [])

    def test_strip_whitespace(self):
        self.create_labels(self.user, ["Blue", "Red"], "Group1")

        self.client.force_login(self.user)
        response = self.client.get(self.url, dict(search="  Blue "))
        self.assertLabels(response, ["Blue"])

    def test_normalize_multiple_spaces(self):
        self.create_labels(
            self.user, ["Light Blue", "Dark Blue", "Dark Red"], "Group1")

        self.client.force_login(self.user)
        response = self.client.get(self.url, dict(search="Dark   Blue"))
        self.assertLabels(response, ["Dark Blue"])

    def test_treat_punctuation_as_spaces(self):
        self.create_labels(
            self.user, ["Light Blue", "Dark Blue", "Dark Red"], "Group1")

        self.client.force_login(self.user)
        response = self.client.get(self.url, dict(search=";'Dark_/Blue=-"))
        self.assertLabels(response, ["Dark Blue"])

    def test_no_tokens(self):
        self.create_labels(
            self.user, ["Light Blue", "Dark Blue", "Dark Red"], "Group1")

        self.client.force_login(self.user)
        response = self.client.get(self.url, dict(search=";'_/=-"))
        self.assertLabels(response, [])


class LabelDetailTest(ClientTest):
    """
    Test the label detail page.
    """
    @classmethod
    def setUpTestData(cls):
        # Call the parent's setup (while still using this class as cls)
        super(LabelDetailTest, cls).setUpTestData()

        cls.user = cls.create_user()

        # Create labels
        cls.labels = cls.create_labels(
            cls.user, ['A', 'B'], "Group1")

    def test_load_page(self):
        """Load the page."""
        response = self.client.get(
            reverse('label_main', kwargs=dict(
                label_id=Label.objects.get(name='B').pk
            ))
        )
        self.assertStatusOK(response)


class LabelDetailPatchesTest(ClientTest):
    """
    Test the example annotation patches used by the label detail page.
    """
    @classmethod
    def setUpTestData(cls):
        # Call the parent's setup (while still using this class as cls)
        super(LabelDetailPatchesTest, cls).setUpTestData()

        cls.user = cls.create_user()
        cls.source = cls.create_source(
            cls.user,
            point_generation_type=PointGen.Types.SIMPLE,
            simple_number_of_points=100,
        )

        cls.labels = cls.create_labels(
            cls.user, ['A', 'B'], "Group1")
        cls.create_labelset(cls.user, cls.source, cls.labels)
        cls.source.refresh_from_db()

        cls.img = cls.upload_image_new(cls.user, cls.source)

    def test_one_page_of_patches(self):
        annotations = {1: 'A', 2: 'A', 3: 'A', 4: 'B', 5: 'B'}
        self.add_annotations(self.user, self.img, annotations)

        response = self.client.get(reverse(
            'label_example_patches_ajax',
            args=[Label.objects.get(name='A').id])).json()

        # 3 patch images
        self.assertEqual(response['patchesHtml'].count('<img'), 3)
        # Is the last page of patches
        self.assertEqual(response['isLastPage'], True)

    def test_multiple_pages_of_patches(self):
        annotations = dict()
        for n in range(1, 10+1):
            annotations[n] = 'B'
        for n in range(11, 63+1):
            annotations[n] = 'A'
        self.add_annotations(self.user, self.img, annotations)

        # Page 1: 50 patch images
        response = self.client.get(reverse(
            'label_example_patches_ajax',
            args=[Label.objects.get(name='A').id])).json()
        self.assertEqual(response['patchesHtml'].count('<img'), 50)
        self.assertEqual(response['isLastPage'], False)

        # Page 2: 3 patch images
        response = self.client.get(
            reverse(
                'label_example_patches_ajax',
                args=[Label.objects.get(name='A').id]),
            dict(page=2),
        ).json()
        self.assertEqual(response['patchesHtml'].count('<img'), 3)
        self.assertEqual(response['isLastPage'], True)

    def test_zero_patches(self):
        annotations = {1: 'B', 2: 'B'}
        self.add_annotations(self.user, self.img, annotations)

        response = self.client.get(reverse(
            'label_example_patches_ajax',
            args=[Label.objects.get(name='A').id])).json()

        self.assertEqual(response['patchesHtml'].count('<img'), 0)
        self.assertEqual(response['isLastPage'], True)


class LabelDetailPatchLinksTest(ClientTest):
    """
    Test the links on the annotation patches.
    """
    @classmethod
    def setUpTestData(cls):
        # Call the parent's setup (while still using this class as cls)
        super(LabelDetailPatchLinksTest, cls).setUpTestData()

        cls.user = cls.create_user()
        cls.users_private_source = cls.create_source(
            cls.user,
            visibility=Source.VisibilityTypes.PRIVATE,
            point_generation_type=PointGen.Types.SIMPLE,
            simple_number_of_points=5,
        )

        cls.user2 = cls.create_user()
        cls.public_source = cls.create_source(
            cls.user2,
            visibility=Source.VisibilityTypes.PUBLIC,
            point_generation_type=PointGen.Types.SIMPLE,
            simple_number_of_points=5,
        )
        cls.other_private_source = cls.create_source(
            cls.user2,
            visibility=Source.VisibilityTypes.PRIVATE,
            point_generation_type=PointGen.Types.SIMPLE,
            simple_number_of_points=5,
        )

        # Create labels
        cls.labels = cls.create_labels(
            cls.user, ['A', 'B'], "Group1")

        # Add all labels to each source's labelset
        cls.create_labelset(cls.user2, cls.public_source, cls.labels)
        cls.public_source.refresh_from_db()
        cls.create_labelset(cls.user, cls.users_private_source, cls.labels)
        cls.users_private_source.refresh_from_db()
        cls.create_labelset(cls.user2, cls.other_private_source, cls.labels)
        cls.other_private_source.refresh_from_db()

        # Upload an image to each source
        cls.public_img = cls.upload_image_new(cls.user2, cls.public_source)
        cls.users_private_img = cls.upload_image_new(
            cls.user, cls.users_private_source)
        cls.other_private_img = cls.upload_image_new(
            cls.user2, cls.other_private_source)

    def test_dont_link_to_others_private_images(self):
        annotations = {1: 'A', 2: 'A', 3: 'A', 4: 'A'}
        self.add_annotations(self.user2, self.public_img, annotations)
        annotations = {1: 'A', 2: 'A'}
        self.add_annotations(self.user, self.users_private_img, annotations)
        annotations = {1: 'A'}
        self.add_annotations(self.user2, self.other_private_img, annotations)

        self.client.force_login(self.user)
        response = self.client.get(reverse(
            'label_example_patches_ajax',
            args=[Label.objects.get(name='A').id])).json()

        # Patches shown: 4 + 2 + 1
        self.assertEqual(response['patchesHtml'].count('<img'), 7)
        # Patches with links: 4 + 2
        self.assertEqual(response['patchesHtml'].count('<a'), 6)


class NewLabelTest(ClientTest):
    """
    Test label creation.
    """
    @classmethod
    def setUpTestData(cls):
        # Call the parent's setup (while still using this class as cls)
        super(NewLabelTest, cls).setUpTestData()

        cls.user = cls.create_user()

        # Create labels and group
        cls.create_labels(
            cls.user, ['A', 'B'], "Group1")

        cls.url = reverse('label_new_ajax')

    def test_load_page_anonymous(self):
        """Redirect to signin page."""
        response = self.client.get(self.url)
        self.assertRedirects(
            response,
            reverse('signin') + '?next=' + self.url,
        )

    def test_label_creation(self):
        """Successfully create a new label."""
        self.client.force_login(self.user)
        response = self.client.post(
            self.url,
            dict(
                name="CCC",
                default_code='C',
                group=LabelGroup.objects.get(code='Group1').pk,
                description="Species C.",
                # A new filename will be generated, and the uploaded
                # filename will be discarded, so it doesn't matter.
                thumbnail=sample_image_as_file('_.png'),
            )
        )
        self.assertStatusOK(response)

        # Check that the label was created, and has the expected field values
        label = Label.objects.get(name="CCC")
        self.assertEqual(label.default_code, 'C')
        self.assertEqual(label.group.code, 'Group1')
        self.assertEqual(label.description, "Species C.")
        self.assertIsNotNone(label.thumbnail)
        self.assertEqual(label.created_by_id, self.user.pk)

    def test_label_name_taken(self):
        """Name taken -> error."""
        self.client.force_login(self.user)
        response = self.client.post(
            self.url,
            dict(
                name="B",
                default_code='B2',
                group=LabelGroup.objects.get(code='Group1').pk,
                description="Species B.",
                # A new filename will be generated, and the uploaded
                # filename will be discarded, so it doesn't matter.
                thumbnail=sample_image_as_file('_.png'),
            ),
        )

        self.assertEqual(response.json(), dict(error=(
            'Name: There is already a label with the same name:'
            ' <a href="{url}" target="_blank">B</a>').format(
                url=reverse(
                    'label_main', args=[Label.objects.get(name="B").pk]))
        ))

    # TODO: Test thumbnail resizing.
