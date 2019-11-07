from __future__ import unicode_literals

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core import mail
from django.shortcuts import resolve_url
from django.test import override_settings
from django.urls import reverse

from images.model_utils import PointGen
from images.models import Source
from lib.tests.utils import ClientTest, sample_image_as_file
from .models import LabelGroup, Label

User = get_user_model()


class LabelTest(ClientTest):

    @classmethod
    def create_label_group(cls, group_name):
        group = LabelGroup(name=group_name, code=group_name[:10])
        group.save()
        return group

    @classmethod
    def create_label(cls, user, name, default_code, group):
        cls.client.force_login(user)
        cls.client.post(
            reverse('label_new_ajax'),
            dict(
                name=name,
                default_code=default_code,
                group=group.pk,
                description="Description",
                # A new filename will be generated, and the uploaded
                # filename will be discarded, so this filename doesn't matter.
                thumbnail=sample_image_as_file('_.png'),
            )
        )
        cls.client.logout()

        return Label.objects.get(name=name)


class LabelListTest(ClientTest):
    """
    Test the label list page.
    """
    @classmethod
    def setUpTestData(cls):
        # Call the parent's setup (while still using this class as cls)
        super(LabelListTest, cls).setUpTestData()

        cls.user = cls.create_user()

        cls.user_committee_member = cls.create_user()
        cls.user_committee_member.groups.add(
            Group.objects.get(name="Labelset Committee"))

        # Create labels
        cls.labels = cls.create_labels(
            cls.user, ['A', 'B'], "Group1")

    def test_load_page(self):
        response = self.client.get(reverse('label_list'))
        self.assertStatusOK(response)

    def test_new_label_link_not_shown_for_regular_user(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('label_list'))
        self.assertNotContains(response, "Create a new label")

    def test_new_label_link_shown_for_committee_member(self):
        self.client.force_login(self.user_committee_member)
        response = self.client.get(reverse('label_list'))
        self.assertContains(response, "Create a new label")


class LabelSearchTest(ClientTest):
    """
    Test label search by Ajax.
    """
    @classmethod
    def setUpTestData(cls):
        # Call the parent's setup (while still using this class as cls)
        super(LabelSearchTest, cls).setUpTestData()

        cls.user = cls.create_user()
        cls.url = reverse('label_list_search_ajax')

    def assertLabels(self, response, label_names):
        response_pk_set = set(response.json()['label_ids'])
        expected_pk_set = set(Label.objects.filter(
            name__in=label_names).values_list('pk', flat=True))
        self.assertSetEqual(response_pk_set, expected_pk_set)

    def submit_search(self, **kwargs):
        data = dict(
            name_search='',
            show_verified=True,
            show_regular=True,
            show_duplicate=False,
            functional_group='',
            min_popularity='',
        )
        data.update(**kwargs)
        response = self.client.get(self.url, data)
        return response

    def test_match_full_name(self):
        self.create_labels(self.user, ["Red", "Blue"], "Group1")

        self.client.force_login(self.user)
        response = self.submit_search(name_search="Red")
        self.assertLabels(response, ["Red"])

    def test_match_part_of_name(self):
        self.create_labels(self.user, ["Red", "Blue"], "Group1")

        self.client.force_login(self.user)
        response = self.submit_search(name_search="Blu")
        self.assertLabels(response, ["Blue"])

    def test_match_case_insensitive(self):
        self.create_labels(self.user, ["Red", "Blue"], "Group1")

        self.client.force_login(self.user)
        response = self.submit_search(name_search="BLUE")
        self.assertLabels(response, ["Blue"])

    def test_match_multiple_labels(self):
        self.create_labels(
            self.user, ["Red", "Light Blue", "Dark Blue"], "Group1")

        self.client.force_login(self.user)
        response = self.submit_search(name_search="Blue")
        self.assertLabels(response, ["Light Blue", "Dark Blue"])

    def test_multiple_words(self):
        self.create_labels(
            self.user, ["Light Blue", "Dark Blue", "Dark Red"], "Group1")

        self.client.force_login(self.user)
        response = self.submit_search(name_search="Dark Blue")
        self.assertLabels(response, ["Dark Blue"])

    def test_no_match(self):
        self.create_labels(self.user, ["Red", "Blue"], "Group1")

        self.client.force_login(self.user)
        response = self.submit_search(name_search="Green")
        self.assertLabels(response, [])

    def test_strip_whitespace(self):
        self.create_labels(self.user, ["Blue", "Red"], "Group1")

        self.client.force_login(self.user)
        response = self.submit_search(name_search="  Blue ")
        self.assertLabels(response, ["Blue"])

    def test_normalize_multiple_spaces(self):
        self.create_labels(
            self.user, ["Light Blue", "Dark Blue", "Dark Red"], "Group1")

        self.client.force_login(self.user)
        response = self.submit_search(name_search="Dark   Blue")
        self.assertLabels(response, ["Dark Blue"])

    def test_treat_punctuation_as_spaces(self):
        self.create_labels(
            self.user, ["Light Blue", "Dark Blue", "Dark Red"], "Group1")

        self.client.force_login(self.user)
        response = self.submit_search(name_search=";'Dark_/Blue=-")
        self.assertLabels(response, ["Dark Blue"])

    def test_no_tokens(self):
        self.create_labels(
            self.user, ["Light Blue", "Dark Blue", "Dark Red"], "Group1")

        self.client.force_login(self.user)
        response = self.submit_search(name_search=";'_/=-")
        self.assertLabels(response, [])

    # TODO: Test filtering on other fields besides name_search


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

        cls.img = cls.upload_image(cls.user, cls.source)

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
        cls.public_img = cls.upload_image(cls.user2, cls.public_source)
        cls.users_private_img = cls.upload_image(
            cls.user, cls.users_private_source)
        cls.other_private_img = cls.upload_image(
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


class NewLabelAjaxTest(ClientTest):
    """
    Test label creation.
    """
    @classmethod
    def setUpTestData(cls):
        # Call the parent's setup (while still using this class as cls)
        super(NewLabelAjaxTest, cls).setUpTestData()

        cls.user = cls.create_user()

        # Create labels and group
        cls.create_labels(
            cls.user, ['A', 'B'], "Group1")

        cls.url = reverse('label_new_ajax')

    def test_load_page_anonymous(self):
        """Redirect to sign-in page."""
        response = self.client.get(self.url)
        self.assertRedirects(
            response,
            reverse(settings.LOGIN_URL) + '?next=' + self.url,
        )

    @override_settings(LABELSET_COMMITTEE_EMAIL='labels@example.com')
    def test_label_creation(self):
        """Successfully create a new label."""
        self.client.force_login(self.user)
        self.client.post(self.url, dict(
            name="CCC",
            default_code='C',
            group=LabelGroup.objects.get(code='Group1').pk,
            description="Species C.",
            # A new filename will be generated, and this uploaded
            # filename will be discarded, so it doesn't matter.
            thumbnail=sample_image_as_file('_.png'),
        ))

        # Check that the label was created, and has the expected field values
        label = Label.objects.get(name="CCC")
        self.assertEqual(label.default_code, 'C')
        self.assertEqual(label.group.code, 'Group1')
        self.assertEqual(label.description, "Species C.")
        self.assertIsNotNone(label.thumbnail)
        self.assertEqual(label.verified, False)
        self.assertEqual(label.created_by_id, self.user.pk)

        # Check that an email was sent out
        self.assertEqual(len(mail.outbox), 1)
        label_email = mail.outbox[-1]
        # Check recipients
        self.assertEqual(len(label_email.to), 1)
        self.assertEqual(label_email.to[0], 'labels@example.com')
        self.assertEqual(len(label_email.cc), 1)
        self.assertEqual(label_email.cc[0], self.user.email)
        # Contents should have the creating user, label name, and link
        # to label details
        self.assertIn(self.user.username, label_email.body)
        self.assertIn("CCC", label_email.body)
        self.assertIn(resolve_url('label_main', label.pk), label_email.body)

    def test_label_name_taken(self):
        """Name taken -> error."""
        self.client.force_login(self.user)
        response = self.client.post(self.url, dict(
            name="B",
            default_code='B2',
            group=LabelGroup.objects.get(code='Group1').pk,
            description="Species B.",
            thumbnail=sample_image_as_file('_.png'),
        ))

        self.assertEqual(response.json(), dict(error=(
            'Name: There is already a label with the same name:'
            ' <a href="{url}" target="_blank">B</a>').format(
                url=reverse(
                    'label_main', args=[Label.objects.get(name="B").pk]))
        ))

    def test_cant_verify(self):
        """Can't set label as verified upon creation."""
        self.client.force_login(self.user)
        self.client.post(self.url, dict(
            name="Label C",
            default_code='C',
            group=LabelGroup.objects.get(code='Group1').pk,
            description="Species C.",
            thumbnail=sample_image_as_file('_.png'),
            verified=True,
        ))

        label = Label.objects.get(name="Label C")
        self.assertEqual(label.verified, False)

    def test_thumbnail_scaled_down(self):
        self.client.force_login(self.user)
        self.client.post(self.url, dict(
            name="Label C",
            default_code='C',
            group=LabelGroup.objects.get(code='Group1').pk,
            description="Species C.",
            thumbnail=sample_image_as_file('_.png', image_options=dict(
                width=Label.THUMBNAIL_WIDTH+100,
                height=Label.THUMBNAIL_HEIGHT+150)),
        ))

        label = Label.objects.get(name="Label C")
        self.assertLessEqual(label.thumbnail.width, Label.THUMBNAIL_WIDTH)
        self.assertLessEqual(label.thumbnail.height, Label.THUMBNAIL_HEIGHT)


class NewLabelNonAjaxTest(ClientTest):

    @classmethod
    def setUpTestData(cls):
        # Call the parent's setup (while still using this class as cls)
        super(NewLabelNonAjaxTest, cls).setUpTestData()

        cls.user = cls.create_user()

        # Create labels and group
        cls.create_labels(
            cls.user, ['A', 'B'], "Group1")

        cls.url = reverse('label_new')

    def test_load_page_anonymous(self):
        """Redirect to sign-in page."""
        response = self.client.get(self.url)
        self.assertRedirects(
            response,
            reverse(settings.LOGIN_URL) + '?next=' + self.url,
        )

    def test_label_creation(self):
        """Successfully create a new label."""
        self.client.force_login(self.user)
        self.client.post(self.url, dict(
            name="CCC",
            default_code='C',
            group=LabelGroup.objects.get(code='Group1').pk,
            description="Species C.",
            # A new filename will be generated, and the uploaded
            # filename will be discarded, so it doesn't matter.
            thumbnail=sample_image_as_file('_.png'),
        ))

        # Check that the label was created, and has the expected field values
        label = Label.objects.get(name="CCC")
        self.assertEqual(label.default_code, 'C')
        self.assertEqual(label.group.code, 'Group1')
        self.assertEqual(label.description, "Species C.")
        self.assertIsNotNone(label.thumbnail)
        self.assertEqual(label.verified, False)
        self.assertEqual(label.created_by_id, self.user.pk)


class EditLabelPermissionTest(ClientTest):

    @classmethod
    def setUpTestData(cls):
        # Call the parent's setup (while still using this class as cls)
        super(EditLabelPermissionTest, cls).setUpTestData()

        cls.user = cls.create_user()

        # Create labels and group
        labels = cls.create_labels(cls.user, ['A', 'B'], "Group1")

        cls.source1 = cls.create_source(cls.user)
        cls.create_labelset(
            cls.user, cls.source1, labels.filter(name__in=['A']))
        cls.source2 = cls.create_source(cls.user)
        cls.create_labelset(
            cls.user, cls.source2, labels.filter(name__in=['A', 'B']))
        cls.source3 = cls.create_source(cls.user)
        cls.create_labelset(
            cls.user, cls.source3, labels.filter(name__in=['B']))

        cls.user_admin_both = cls.create_user()
        cls.add_source_member(
            cls.user, cls.source1,
            cls.user_admin_both, Source.PermTypes.ADMIN.code)
        cls.add_source_member(
            cls.user, cls.source2,
            cls.user_admin_both, Source.PermTypes.ADMIN.code)

        cls.user_admin_one = cls.create_user()
        cls.add_source_member(
            cls.user, cls.source1,
            cls.user_admin_one, Source.PermTypes.ADMIN.code)

        cls.user_editor_both = cls.create_user()
        cls.add_source_member(
            cls.user, cls.source1,
            cls.user_editor_both, Source.PermTypes.EDIT.code)
        cls.add_source_member(
            cls.user, cls.source2,
            cls.user_editor_both, Source.PermTypes.EDIT.code)

        cls.user_committee_member = cls.create_user()
        cls.user_committee_member.groups.add(
            Group.objects.get(name="Labelset Committee"))

        # Verify label B
        label_B = labels.get(name='B')
        label_B.verified = True
        label_B.save()

        cls.url = reverse('label_edit', args=[labels.get(name='A').pk])
        cls.url_verified = reverse(
            'label_edit', args=[labels.get(name='B').pk])

    def test_anonymous(self):
        response = self.client.get(self.url)
        self.assertTemplateUsed(response, self.PERMISSION_DENIED_TEMPLATE)

    def test_admin_of_one_source_using_the_label(self):
        self.client.force_login(self.user_admin_one)
        response = self.client.get(self.url)
        self.assertTemplateUsed(response, self.PERMISSION_DENIED_TEMPLATE)

    def test_editor_of_all_sources_using_the_label(self):
        self.client.force_login(self.user_editor_both)
        response = self.client.get(self.url)
        self.assertTemplateUsed(response, self.PERMISSION_DENIED_TEMPLATE)

    def test_admin_of_all_sources_using_the_label(self):
        self.client.force_login(self.user_admin_both)
        response = self.client.get(self.url)
        self.assertTemplateUsed(response, 'labels/label_edit.html')

    def test_admin_of_all_sources_using_verified_label(self):
        self.client.force_login(self.user_editor_both)
        response = self.client.get(self.url_verified)
        self.assertTemplateUsed(response, self.PERMISSION_DENIED_TEMPLATE)

    def test_labelset_committee_member(self):
        self.client.force_login(self.user_committee_member)
        response = self.client.get(self.url_verified)
        self.assertTemplateUsed(response, 'labels/label_edit.html')

    def test_superuser(self):
        self.client.force_login(User.objects.get(username='superuser'))
        response = self.client.get(self.url_verified)
        self.assertTemplateUsed(response, 'labels/label_edit.html')


class EditLabelTest(LabelTest):
    """
    Test label editing.
    """
    @classmethod
    def setUpTestData(cls):
        # Call the parent's setup (while still using this class as cls)
        super(EditLabelTest, cls).setUpTestData()

        cls.user = cls.create_user()

        cls.user_committee_member = cls.create_user()
        cls.user_committee_member.groups.add(
            Group.objects.get(name="Labelset Committee"))

        # Create labels and groups
        cls.group1 = cls.create_label_group("Group1")
        cls.group2 = cls.create_label_group("Group2")
        cls.labels = dict(
            A=cls.create_label(cls.user, "Label A", 'A', cls.group1),
            B=cls.create_label(cls.user, "Label B", 'B', cls.group1),
            C=cls.create_label(cls.user, "Label C", 'C', cls.group1),
        )
        # Ensure cls.user 'owns' the labels
        cls.source = cls.create_source(cls.user)
        cls.create_labelset(
            cls.user, cls.source, Label.objects.all())

        cls.url = reverse('label_edit', args=[cls.labels['A'].pk])

    def test_name_same(self):
        self.client.force_login(self.user)
        response = self.client.post(self.url, follow=True, data=dict(
            name="Label A",
            default_code='A',
            group=self.labels['A'].group.pk,
            description=self.labels['A'].description,
        ))
        self.assertContains(response, "Label successfully edited.")

    def test_name_change_case_only(self):
        self.client.force_login(self.user)
        self.client.post(self.url, follow=True, data=dict(
            name="LABEL a",
            default_code='A',
            group=self.labels['A'].group.pk,
            description=self.labels['A'].description,
        ))

        self.labels['A'].refresh_from_db()
        self.assertEqual(self.labels['A'].name, "LABEL a")

    def test_name_change(self):
        self.client.force_login(self.user)
        self.client.post(self.url, follow=True, data=dict(
            name="Label Alpha",
            default_code='A',
            group=self.labels['A'].group.pk,
            description=self.labels['A'].description,
        ))

        self.labels['A'].refresh_from_db()
        self.assertEqual(self.labels['A'].name, "Label Alpha")

    def test_name_conflict(self):
        self.client.force_login(self.user)
        response = self.client.post(self.url, follow=True, data=dict(
            name="LABEL B",
            default_code='A',
            group=self.labels['A'].group.pk,
            description=self.labels['A'].description,
        ))
        self.assertContains(
            response,
            'There is already a label with the same name:'
            ' <a href="{url}" target="_blank">'
            '{conflicting_name}</a>'.format(
                url=reverse('label_main', args=[self.labels['B'].pk]),
                conflicting_name="Label B"))
        # Check for no change
        self.labels['A'].refresh_from_db()
        self.assertEqual(self.labels['A'].name, "Label A")

    def test_default_code_same(self):
        self.client.force_login(self.user)
        response = self.client.post(self.url, follow=True, data=dict(
            name="Label A",
            default_code='A',
            group=self.labels['A'].group.pk,
            description=self.labels['A'].description,
        ))
        self.assertContains(response, "Label successfully edited.")

    def test_default_code_change_case_only(self):
        self.client.force_login(self.user)
        self.client.post(self.url, follow=True, data=dict(
            name="Label A",
            default_code='a',
            group=self.labels['A'].group.pk,
            description=self.labels['A'].description,
        ))

        self.labels['A'].refresh_from_db()
        self.assertEqual(self.labels['A'].default_code, 'a')

    def test_default_code_change(self):
        self.client.force_login(self.user)
        self.client.post(self.url, follow=True, data=dict(
            name="Label A",
            default_code='Alpha',
            group=self.labels['A'].group.pk,
            description=self.labels['A'].description,
        ))

        self.labels['A'].refresh_from_db()
        self.assertEqual(self.labels['A'].default_code, 'Alpha')

    def test_default_code_conflict(self):
        self.client.force_login(self.user)
        response = self.client.post(self.url, follow=True, data=dict(
            name="Label A",
            default_code='b',
            group=self.labels['A'].group.pk,
            description=self.labels['A'].description,
        ))
        self.assertContains(
            response,
            'There is already a label with the same default code:'
            ' <a href="{url}" target="_blank">'
            '{conflicting_code}</a>'.format(
                url=reverse('label_main', args=[self.labels['B'].pk]),
                conflicting_code="B"))
        # Check for no change
        self.labels['A'].refresh_from_db()
        self.assertEqual(self.labels['A'].default_code, 'A')

    def test_group_change(self):
        self.client.force_login(self.user)
        self.client.post(self.url, follow=True, data=dict(
            name="Label A",
            default_code='A',
            group=self.group2.pk,
            description=self.labels['A'].description,
        ))

        self.labels['A'].refresh_from_db()
        self.assertEqual(self.labels['A'].group.pk, self.group2.pk)

    def test_description_change(self):
        self.client.force_login(self.user)
        self.client.post(self.url, follow=True, data=dict(
            name="Label A",
            default_code='A',
            group=self.labels['A'].group.pk,
            description="Another\ndescription",
        ))

        self.labels['A'].refresh_from_db()
        self.assertEqual(self.labels['A'].description, "Another\ndescription")

    def test_thumbnail_change(self):
        original_filename = self.labels['A'].thumbnail.name

        self.client.force_login(self.user)
        self.client.post(self.url, follow=True, data=dict(
            name="Label A",
            default_code='A',
            group=self.labels['A'].group.pk,
            description=self.labels['A'].description,
            thumbnail=sample_image_as_file('_.png'),
        ))

        # Check for a different thumbnail file, by checking filename.
        # This assumes the filenames are designed to not clash
        # (e.g. qoxibnwke9.jpg) rather than replace each other
        # (e.g. thumbnail-for-label-29.jpg).
        self.labels['A'].refresh_from_db()
        self.assertNotEqual(original_filename, self.labels['A'].thumbnail.name)

    def test_verified_change(self):
        self.client.force_login(self.user_committee_member)
        self.client.post(self.url, follow=True, data=dict(
            name="Label A",
            default_code='A',
            group=self.labels['A'].group.pk,
            description=self.labels['A'].description,
            verified=True,
        ))

        self.labels['A'].refresh_from_db()
        self.assertEqual(self.labels['A'].verified, True)

    def test_verified_requires_permission(self):
        # Non committee member
        self.client.force_login(self.user)
        self.client.post(self.url, follow=True, data=dict(
            name="Label A",
            default_code='A',
            group=self.labels['A'].group.pk,
            description=self.labels['A'].description,
            verified=True,
        ))

        self.labels['A'].refresh_from_db()
        # Not changed
        self.assertEqual(self.labels['A'].verified, False)
