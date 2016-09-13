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

        # Create source (required to reach new-label form)
        cls.source = cls.create_source(cls.user)

        # Create labels
        cls.labels = cls.create_labels(
            cls.user, ['A', 'B'], "Group1")

    def test_load_page(self):
        """Load the page."""
        response = self.client.get(reverse('label_list'))
        self.assertStatusOK(response)


class LabelDetailTest(ClientTest):
    """
    Test the label detail page.
    """
    @classmethod
    def setUpTestData(cls):
        # Call the parent's setup (while still using this class as cls)
        super(LabelDetailTest, cls).setUpTestData()

        cls.user = cls.create_user()

        # Create source (required to reach new-label form)
        cls.source = cls.create_source(cls.user)

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
    Test the annotation patches of the label detail page.
    """
    @classmethod
    def setUpTestData(cls):
        # Call the parent's setup (while still using this class as cls)
        super(LabelDetailPatchesTest, cls).setUpTestData()

        cls.user = cls.create_user()

        # Create 1 public and 1 private source
        cls.public_source = cls.create_source(
            cls.user,
            visibility=Source.VisibilityTypes.PUBLIC,
            point_generation_type=PointGen.Types.SIMPLE,
            simple_number_of_points=10,
        )
        cls.private_source = cls.create_source(
            cls.user,
            visibility=Source.VisibilityTypes.PRIVATE,
            point_generation_type=PointGen.Types.SIMPLE,
            simple_number_of_points=10,
        )

        # Create labels
        cls.labels = cls.create_labels(
            cls.user, ['A', 'B'], "Group1")

        # Add all labels to each source's labelset
        cls.create_labelset(cls.user, cls.public_source, cls.labels)
        cls.public_source.refresh_from_db()
        cls.create_labelset(cls.user, cls.private_source, cls.labels)
        cls.private_source.refresh_from_db()

        # Upload an image to each source
        cls.public_image = cls.upload_image_new(cls.user, cls.public_source)
        cls.private_image = cls.upload_image_new(cls.user, cls.private_source)

    def test_five_patches(self):
        """
        Over 5 annotations in public sources. Display only 5 patches.
        """
        annotations = {1: 'A', 2: 'A', 3: 'A', 4: 'A', 5: 'A', 6: 'A'}
        self.add_annotations(self.user, self.public_image, annotations)

        response = self.client.get(
            reverse('label_main', kwargs=dict(
                label_id=Label.objects.get(name='A').id
            ))
        )
        self.assertStatusOK(response)
        self.assertEqual(len(response.context['patches']), 5)

    def test_less_than_five_patches(self):
        """
        Under 5 annotations in public sources. Display that many patches.
        """
        annotations = {1: 'A', 2: 'A', 3: 'A', 4: 'B', 5: 'B'}
        self.add_annotations(self.user, self.public_image, annotations)

        response = self.client.get(
            reverse('label_main', kwargs=dict(
                label_id=Label.objects.get(name='A').id
            ))
        )
        self.assertStatusOK(response)
        self.assertEqual(len(response.context['patches']), 3)

    def test_zero_patches(self):
        """
        0 annotations in public sources. Display 0 patches.
        """
        annotations = {}
        self.add_annotations(self.user, self.public_image, annotations)

        response = self.client.get(
            reverse('label_main', kwargs=dict(
                label_id=Label.objects.get(name='A').id
            ))
        )
        self.assertStatusOK(response)
        self.assertEqual(len(response.context['patches']), 0)

    def test_dont_include_private_sources(self):
        """
        3 public, 2 private. Display 3 patches.
        """
        annotations = {1: 'A', 2: 'A', 3: 'A'}
        self.add_annotations(self.user, self.public_image, annotations)
        annotations = {1: 'A', 2: 'A'}
        self.add_annotations(self.user, self.private_image, annotations)

        response = self.client.get(
            reverse('label_main', kwargs=dict(
                label_id=Label.objects.get(name='A').id
            ))
        )
        self.assertEqual(len(response.context['patches']), 3)


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
            'Error: Name: There is already a label with the same name:'
            ' <a href="{url}" target="_blank">B</a>').format(
                url=reverse(
                    'label_main', args=[Label.objects.get(name="B").pk]))
        ))

    # TODO: Test thumbnail resizing.


class LabelsetAddPermissionTest(ClientTest):
    """
    Test the new labelset page.
    """
    @classmethod
    def setUpTestData(cls):
        # Call the parent's setup (while still using this class as cls)
        super(LabelsetAddPermissionTest, cls).setUpTestData()

        cls.user = cls.create_user()

        # Create source (required to reach new-label form)
        cls.source = cls.create_source(cls.user)

        cls.user_viewer = cls.create_user()
        cls.add_source_member(
            cls.user, cls.source, cls.user_viewer, Source.PermTypes.VIEW.code)
        cls.user_editor = cls.create_user()
        cls.add_source_member(
            cls.user, cls.source, cls.user_editor, Source.PermTypes.EDIT.code)

        # Create labels and group
        cls.create_labels(
            cls.user, ['A', 'B', 'C'], "Group1")

        cls.url = reverse('labelset_add', args=[cls.source.pk])

    def test_load_page_anonymous(self):
        """Don't have permission."""
        response = self.client.get(self.url)
        self.assertStatusOK(response)
        self.assertTemplateUsed(response, self.PERMISSION_DENIED_TEMPLATE)

    def test_load_page_as_source_viewer(self):
        """Don't have permission."""
        self.client.force_login(self.user_viewer)
        response = self.client.get(self.url)
        self.assertStatusOK(response)
        self.assertTemplateUsed(response, self.PERMISSION_DENIED_TEMPLATE)

    def test_load_page_as_source_editor(self):
        """Don't have permission."""
        self.client.force_login(self.user_editor)
        response = self.client.get(self.url)
        self.assertStatusOK(response)
        self.assertTemplateUsed(response, self.PERMISSION_DENIED_TEMPLATE)

    def test_load_page_as_source_admin(self):
        """Page loads normally."""
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        self.assertStatusOK(response)
        self.assertTemplateUsed(response, 'labels/labelset_add.html')


class LabelsetCreateTest(ClientTest):
    """
    Test the new labelset page.
    """
    @classmethod
    def setUpTestData(cls):
        # Call the parent's setup (while still using this class as cls)
        super(LabelsetCreateTest, cls).setUpTestData()

        cls.user = cls.create_user()

        # Create source (required to reach new-label form)
        cls.source = cls.create_source(cls.user)

        # Create labels and group
        cls.create_labels(
            cls.user, ['A', 'B', 'C'], "Group1")

        cls.url = reverse('labelset_add', args=[cls.source.pk])

    def test_success(self):
        """Successfully create a new labelset."""

        # These are the labels we'll try putting into the labelset.
        label_pks = [
            Label.objects.get(name=name).pk
            for name in ["A", "B"]
        ]

        self.client.force_login(self.user)
        response = self.client.post(
            self.url,
            dict(label_ids=','.join(str(pk) for pk in label_pks)),
            follow=True,
        )
        self.assertContains(response, "Labelset successfully created.")

        url = reverse('labelset_main', args=[self.source.pk])
        self.assertRedirects(response, url)

        # Check the new labelset for the expected labels.
        self.source.refresh_from_db()
        # Check codes.
        self.assertSetEqual(
            {label.code for label in self.source.labelset.get_labels()},
            {'A', 'B'},
        )
        # Check foreign keys to globals.
        self.assertSetEqual(
            {label.pk for label in self.source.labelset.get_globals()},
            set(label_pks),
        )

    def test_no_labels(self):
        """No labels -> error."""
        self.client.force_login(self.user)
        response = self.client.post(
            self.url,
            dict(label_ids=''),
        )
        self.assertContains(response, "You must select one or more labels.")

        self.source.refresh_from_db()
        self.assertIsNone(self.source.labelset)


class LabelsetAddRemoveTest(ClientTest):
    """
    Test adding/removing labels from a labelset.
    """
    @classmethod
    def setUpTestData(cls):
        # Call the parent's setup (while still using this class as cls)
        super(LabelsetAddRemoveTest, cls).setUpTestData()

        cls.user = cls.create_user()

        # Create source (required to reach new-label form)
        cls.source = cls.create_source(cls.user)

        # Create labels and group
        labels = cls.create_labels(
            cls.user, ['A', 'B', 'C', 'D', 'E'], "Group1")
        cls.create_labelset(cls.user, cls.source, labels.filter(
            name__in=['A', 'B', 'C']))

        cls.url = reverse('labelset_add', args=[cls.source.pk])

    def test_add(self):
        """
        Add labels.
        """
        label_pks = [
            Label.objects.get(name=name).pk
            for name in ['A', 'B', 'C', 'D', 'E']
        ]
        self.client.force_login(self.user)
        response = self.client.post(
            self.url,
            dict(label_ids=','.join(str(pk) for pk in label_pks)),
            follow=True,
        )
        self.assertContains(response, "Labelset successfully changed.")

        # Check the edited labelset for the expected labels.
        self.source.labelset.refresh_from_db()
        self.assertSetEqual(
            set(self.source.labelset.get_labels().values_list(
                'code', flat=True)),
            {'A', 'B', 'C', 'D', 'E'},
        )

    def test_remove(self):
        """
        Remove labels.
        """
        label_pks = [
            Label.objects.get(name=name).pk
            for name in ['A']
        ]
        self.client.force_login(self.user)
        response = self.client.post(
            self.url,
            dict(label_ids=','.join(str(pk) for pk in label_pks)),
            follow=True,
        )
        self.assertContains(response, "Labelset successfully changed.")

        # Check the edited labelset for the expected labels.
        self.source.labelset.refresh_from_db()
        self.assertSetEqual(
            set(self.source.labelset.get_labels().values_list(
                'code', flat=True)),
            {'A'},
        )

    def test_add_and_remove(self):
        """
        Add some labels, remove others.
        """
        label_pks = [
            Label.objects.get(name=name).pk
            for name in ['C', 'D', 'E']
        ]
        self.client.force_login(self.user)
        response = self.client.post(
            self.url,
            dict(label_ids=','.join(str(pk) for pk in label_pks)),
            follow=True,
        )
        self.assertContains(response, "Labelset successfully changed.")

        # Check the edited labelset for the expected labels.
        self.source.labelset.refresh_from_db()
        self.assertSetEqual(
            set(self.source.labelset.get_labels().values_list(
                'code', flat=True)),
            {'C', 'D', 'E'},
        )
