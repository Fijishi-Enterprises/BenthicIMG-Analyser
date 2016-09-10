import os

from django.conf import settings
from django.core.urlresolvers import reverse
from django.db.models import Count

from images.model_utils import PointGen
from images.models import Source
from labels.models import LabelGroup, Label, LabelSet
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
            cls.user, cls.source, ['A', 'B'], "Group1")

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
            cls.user, cls.source, ['A', 'B'], "Group1")

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
            cls.user, cls.public_source, ['A', 'B'], "Group1")

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


# class NewLabelTest(ClientTest):
#     """
#     As long as the new label page still exists, at least check that it
#     doesn't let in anonymous users.
#     """
#     fixtures = ['test_labels.yaml']
#
#     def test_load_page_anonymous(self):
#         """Load the page while logged out -> sign-in prompt."""
#         response = self.client.get(reverse('label_new'))
#         self.assertRedirects(
#             response,
#             reverse('signin')+'?next='+reverse('label_new'),
#         )


class NewLabelsetTest(ClientTest):
    """
    Test the new labelset page.
    """
    @classmethod
    def setUpTestData(cls):
        # Call the parent's setup (while still using this class as cls)
        super(NewLabelsetTest, cls).setUpTestData()

        cls.user = cls.create_user()

        # Create source (required to reach new-label form)
        cls.source = cls.create_source(cls.user)

        # Create labels and group
        cls.create_labels(
            cls.user, cls.source, ['A', 'B'], "Group1")

        cls.url = reverse('labelset_new', args=[cls.source.pk])

#     def test_load_page_anonymous(self):
#         """
#         Load the page while logged out ->
#         sorry, don't have permission.
#         """
#         url = reverse('labelset_new', kwargs=dict(
#             source_id=Source.objects.get(name='public1').pk
#         ))
#         response = self.client.get(url)
#         self.assertStatusOK(response)
#         self.assertTemplateUsed(response, self.PERMISSION_DENIED_TEMPLATE)
#
#     def test_load_page_as_source_outsider(self):
#         """
#         Load the page as a user outside the source ->
#         sorry, don't have permission.
#         """
#         self.client.login(username='user2', password='secret')
#
#         url = reverse('labelset_new', kwargs=dict(
#             source_id=Source.objects.get(name='public1').pk
#         ))
#         response = self.client.get(url)
#         self.assertStatusOK(response)
#         self.assertTemplateUsed(response, self.PERMISSION_DENIED_TEMPLATE)
#
#     def test_load_page_as_source_editor(self):
#         """
#         Load the page as a source editor ->
#         sorry, don't have permission.
#         """
#         self.client.login(username='user3', password='secret')
#
#         url = reverse('labelset_new', kwargs=dict(
#             source_id=Source.objects.get(name='public1').pk
#         ))
#         response = self.client.get(url)
#         self.assertStatusOK(response)
#         self.assertTemplateUsed(response, self.PERMISSION_DENIED_TEMPLATE)
#
#     def test_load_page_as_source_admin(self):
#         """
#         Load the page as a source admin -> page loads normally.
#         """
#         self.client.login(username='user4', password='secret')
#
#         url = reverse('labelset_new', kwargs=dict(
#             source_id=Source.objects.get(name='public1').pk
#         ))
#         response = self.client.get(url)
#         self.assertStatusOK(response)
#         self.assertTemplateUsed(response, 'labels/labelset_new.html')

    def test_label_creation(self):
        """Successfully create a new label."""
        self.client.force_login(self.user)
        response = self.client.post(
            self.url,
            dict(
                # create_label triggers the new-label form.
                # The key just needs to be there in the POST;
                # the value doesn't matter.
                create_label='.',
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

    # TODO: Test thumbnail resizing.

    def test_labelset_creation(self):
        """Successfully create a new labelset."""

        # These are the labels we'll try putting into the labelset.
        label_pks = [
            Label.objects.get(name=name).pk
            for name in ["A", "B"]
        ]

        self.client.force_login(self.user)
        response = self.client.post(
            self.url,
            dict(
                # create_labelset indicates that the new-labelset form should
                # be used, not the new-label form which is also on the page.
                # The key just needs to be there in the POST;
                # the value doesn't matter.
                create_labelset='.',
                label_ids=','.join(str(pk) for pk in label_pks),
            ),
            follow=True,
        )

        url = reverse('labelset_main', args=[self.source.pk])
        self.assertRedirects(response, url)

        # Check the new labelset for the expected labels.
        self.source.refresh_from_db()
        self.assertSetEqual(
            {label.code for label in self.source.labelset.get_labels()},
            {'A', 'B'},
        )


class EditLabelsetTest(ClientTest):
    """
    Test the edit labelset page.
    """
    @classmethod
    def setUpTestData(cls):
        # Call the parent's setup (while still using this class as cls)
        super(EditLabelsetTest, cls).setUpTestData()

        cls.user = cls.create_user()

        # Create source (required to reach new-label form)
        cls.source = cls.create_source(cls.user)

        # Create labels and group
        cls.create_labels(
            cls.user, cls.source, ['A', 'B', 'C'], "Group1")

        cls.url = reverse('labelset_edit', args=[cls.source.pk])

#     def test_load_page_anonymous(self):
#         """
#         Load the page while logged out ->
#         sorry, don't have permission.
#         """
#         url = reverse('labelset_edit', kwargs=dict(
#             source_id=Source.objects.get(name='public1').pk
#         ))
#         response = self.client.get(url)
#         self.assertStatusOK(response)
#         self.assertTemplateUsed(response, self.PERMISSION_DENIED_TEMPLATE)
#
#     def test_load_page_as_source_outsider(self):
#         """
#         Load the page as a user outside the source ->
#         sorry, don't have permission.
#         """
#         self.client.login(username='user2', password='secret')
#
#         url = reverse('labelset_edit', kwargs=dict(
#             source_id=Source.objects.get(name='public1').pk
#         ))
#         response = self.client.get(url)
#         self.assertStatusOK(response)
#         self.assertTemplateUsed(response, self.PERMISSION_DENIED_TEMPLATE)
#
#     def test_load_page_as_source_editor(self):
#         """
#         Load the page as a source editor ->
#         sorry, don't have permission.
#         """
#         self.client.login(username='user3', password='secret')
#
#         url = reverse('labelset_edit', kwargs=dict(
#             source_id=Source.objects.get(name='public1').pk
#         ))
#         response = self.client.get(url)
#         self.assertStatusOK(response)
#         self.assertTemplateUsed(response, self.PERMISSION_DENIED_TEMPLATE)
#
#     def test_load_page_with_no_labelset(self):
#         """
#         Load the page as a source admin, but with no labelset on the source ->
#         redirect to new labelset page.
#         """
#         self.client.login(username='user4', password='secret')
#
#         edit_url = reverse('labelset_edit', kwargs=dict(
#             source_id=Source.objects.get(name='public1').pk
#         ))
#         new_url = reverse('labelset_new', kwargs=dict(
#             source_id=Source.objects.get(name='public1').pk
#         ))
#         response = self.client.get(edit_url)
#         self.assertRedirects(response, new_url)
#
#     def test_load_page_with_labelset(self):
#         """
#         Load the page as a source admin, with a labelset on the source ->
#         page loads normally.
#         """
#         # Ensure our source has a non-empty labelset.
#         # Here we query for labelsets with more than 0 labels.
#         # Source: http://stackoverflow.com/a/5080597/
#         labelsets = LabelSet.objects.annotate(num_labels=Count('labels'))
#         a_non_empty_labelset = labelsets.filter(num_labels__gt=0)[0]
#         source = Source.objects.get(name='public1')
#         source.labelset = a_non_empty_labelset
#         source.save()
#
#         self.client.login(username='user4', password='secret')
#
#         url = reverse('labelset_edit', kwargs=dict(
#             source_id=Source.objects.get(name='public1').pk
#         ))
#         response = self.client.get(url)
#         self.assertStatusOK(response)
#         self.assertTemplateUsed(response, 'labels/labelset_edit.html')

    def test_edit_success(self):
        """
        Edit the labelset successfully.
        """
        # Create labelset
        labels = Label.objects.filter(name__in=["A", "B"])
        self.create_labelset(
            self.user, self.source, labels)

        detail_url = reverse('labelset_main', args=[self.source.pk])

        # Edit labelset
        label_pks = [
            Label.objects.get(name=name).pk
            for name in ["B", "C"]
        ]
        self.client.force_login(self.user)
        response = self.client.post(
            self.url,
            # edit_labelset indicates that the edit-labelset form should
            # be used, not the new-label form which is also on the page.
            # The key just needs to be there in the POST;
            # the value doesn't matter.
            dict(
                edit_labelset='.',
                label_ids=','.join(str(pk) for pk in label_pks),
            ),
        )

        # Should redirect to the labelset viewing page.
        self.assertRedirects(response, detail_url)

        # Check the edited labelset for the expected labels.
        self.source.labelset.refresh_from_db()
        self.assertSetEqual(
            set(self.source.labelset.get_labels().values('code', flat=True)),
            {'B', 'C'},
        )

    # TODO: Check that the new label form works.
    # TODO: Check that the cancel button works.
