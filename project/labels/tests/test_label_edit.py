from django.contrib.auth.models import Group
from django.urls import reverse

from images.models import Source
from lib.tests.utils import BasePermissionTest, sample_image_as_file
from ..models import Label
from .utils import LabelTest


class EditLabelPermissionTest(BasePermissionTest):

    @classmethod
    def setUpTestData(cls):
        super(EditLabelPermissionTest, cls).setUpTestData()

        # Create labels and group
        labels = cls.create_labels(cls.user, ['A', 'B', 'C'], "Group1")

        cls.source1 = cls.create_source(cls.user)
        cls.create_labelset(
            cls.user, cls.source1, labels.filter(name__in=['A', 'B']))
        cls.source2 = cls.create_source(cls.user)
        cls.create_labelset(
            cls.user, cls.source2, labels.filter(name__in=['A', 'B']))
        cls.source3 = cls.create_source(cls.user)
        cls.create_labelset(
            cls.user, cls.source3, labels.filter(name__in=['C']))

        label_b = labels.get(name='B')
        label_b.verified = True
        label_b.save()

        cls.url = reverse('label_edit', args=[labels.get(name='A').pk])
        cls.url_verified = reverse('label_edit', args=[label_b.pk])

    def test_anonymous(self):
        self.assertPermissionDenied(self.url, None)

    def test_admin_of_one_source_using_the_label(self):
        user_admin_one = self.create_user()
        self.add_source_member(
            self.user, self.source1,
            user_admin_one, Source.PermTypes.ADMIN.code)

        # Must be admin of all sources using the label, not just one.
        self.assertPermissionDenied(self.url, user_admin_one)

    def test_editor_of_all_sources_using_the_label(self):
        user_editor_both = self.create_user()
        self.add_source_member(
            self.user, self.source1,
            user_editor_both, Source.PermTypes.EDIT.code)
        self.add_source_member(
            self.user, self.source2,
            user_editor_both, Source.PermTypes.EDIT.code)

        # Edit isn't enough, must be admin.
        self.assertPermissionDenied(self.url, user_editor_both)

    def test_admin_of_all_sources_using_the_label(self):
        user_admin_both = self.create_user()
        self.add_source_member(
            self.user, self.source1,
            user_admin_both, Source.PermTypes.ADMIN.code)
        self.add_source_member(
            self.user, self.source2,
            user_admin_both, Source.PermTypes.ADMIN.code)

        self.assertPermissionGranted(
            self.url, user_admin_both, template='labels/label_edit.html')

    def test_admin_of_all_sources_using_verified_label(self):
        user_admin_both = self.create_user()
        self.add_source_member(
            self.user, self.source1,
            user_admin_both, Source.PermTypes.ADMIN.code)
        self.add_source_member(
            self.user, self.source2,
            user_admin_both, Source.PermTypes.ADMIN.code)

        # Being source admin isn't enough for verified labels.
        self.assertPermissionDenied(self.url_verified, user_admin_both)

    def test_labelset_committee_member(self):
        user_committee_member = self.create_user()
        user_committee_member.groups.add(
            Group.objects.get(name="Labelset Committee"))

        # Committee members can edit verified labels.
        self.assertPermissionGranted(
            self.url_verified, user_committee_member,
            template='labels/label_edit.html')

    def test_superuser(self):
        self.assertPermissionGranted(
            self.url_verified, self.superuser,
            template='labels/label_edit.html')


class EditLabelTest(LabelTest):
    """
    Test label editing.
    """
    @classmethod
    def setUpTestData(cls):
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

    def submit_edit(self, user=None, **params):
        # Defaults
        post_data = dict(
            name="Label A",
            default_code='A',
            group=self.labels['A'].group.pk,
            description=self.labels['A'].description,
        )
        post_data.update(params)

        self.client.force_login(user or self.user)
        response = self.client.post(
            reverse('label_edit', args=[self.labels['A'].pk]),
            data=post_data, follow=True)
        return response

    def test_name_same(self):
        response = self.submit_edit(name="Label A")

        self.assertContains(response, "Label successfully edited.")

    def test_name_change_case_only(self):
        self.submit_edit(name="LABEL a")

        self.labels['A'].refresh_from_db()
        self.assertEqual(self.labels['A'].name, "LABEL a")

    def test_name_change(self):
        self.submit_edit(name="Label Alpha")

        self.labels['A'].refresh_from_db()
        self.assertEqual(self.labels['A'].name, "Label Alpha")

    def test_name_conflict(self):
        response = self.submit_edit(name="LABEL B")

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
        response = self.submit_edit(default_code='A')

        self.assertContains(response, "Label successfully edited.")

    def test_default_code_change_case_only(self):
        self.submit_edit(default_code='a')

        self.labels['A'].refresh_from_db()
        self.assertEqual(self.labels['A'].default_code, 'a')

    def test_default_code_change(self):
        self.submit_edit(default_code='Alpha')

        self.labels['A'].refresh_from_db()
        self.assertEqual(self.labels['A'].default_code, 'Alpha')

    def test_default_code_conflict(self):
        response = self.submit_edit(default_code='b')

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
        self.submit_edit(group=self.group2.pk)

        self.labels['A'].refresh_from_db()
        self.assertEqual(self.labels['A'].group.pk, self.group2.pk)

    def test_description_change(self):
        self.submit_edit(description="Another\ndescription")

        self.labels['A'].refresh_from_db()
        self.assertEqual(self.labels['A'].description, "Another\ndescription")

    def test_thumbnail_change(self):
        original_filename = self.labels['A'].thumbnail.name

        self.submit_edit(thumbnail=sample_image_as_file('_.png'))

        # Check for a different thumbnail file, by checking filename.
        # This assumes the filenames are designed to not clash
        # (e.g. qoxibnwke9.jpg) rather than replace each other
        # (e.g. thumbnail-for-label-29.jpg).
        self.labels['A'].refresh_from_db()
        self.assertNotEqual(original_filename, self.labels['A'].thumbnail.name)

    def test_verified_change(self):
        self.submit_edit(
            user=self.user_committee_member,
            verified=True)

        self.labels['A'].refresh_from_db()
        self.assertEqual(self.labels['A'].verified, True)

    def test_verified_requires_permission(self):
        # Non committee member
        self.submit_edit(
            user=self.user,
            verified=True)

        self.labels['A'].refresh_from_db()
        # Not changed
        self.assertEqual(self.labels['A'].verified, False)

    def test_duplicate_change(self):
        # Must verify B to make it a candidate for a duplicate pointer
        self.labels['B'].verified = True
        self.labels['B'].save()

        response = self.submit_edit(
            user=self.user_committee_member,
            duplicate=self.labels['B'].pk)

        self.assertContains(response, "Label successfully edited.")
        self.labels['A'].refresh_from_db()
        self.assertEqual(self.labels['A'].duplicate.pk, self.labels['B'].pk)

    def test_duplicate_requires_permission(self):
        # Must verify B to make it a candidate for a duplicate pointer
        self.labels['B'].verified = True
        self.labels['B'].save()

        response = self.submit_edit(
            user=self.user,
            duplicate=self.labels['B'].pk)

        # Still expect to show success, but with the duplicate field ignored
        self.assertContains(response, "Label successfully edited.")

        self.labels['A'].refresh_from_db()
        # Not changed
        self.assertEqual(self.labels['A'].duplicate, None)

    def test_duplicate_cant_point_to_unverified(self):
        self.labels['B'].verified = False
        self.labels['B'].save()

        response = self.submit_edit(
            user=self.user_committee_member,
            duplicate=self.labels['B'].pk)

        self.assertContains(response, "Please correct the errors below.")
        self.assertContains(
            response,
            "Select a valid choice. That choice is not one of the available"
            " choices.")

        self.labels['A'].refresh_from_db()
        # Not changed
        self.assertEqual(self.labels['A'].duplicate, None)

    def test_duplicate_cant_be_verified(self):
        self.labels['B'].verified = True
        self.labels['B'].save()

        response = self.submit_edit(
            user=self.user_committee_member,
            verified=True,
            duplicate=self.labels['B'].pk)

        self.assertContains(response, "Please correct the errors below.")
        self.assertContains(
            response, "A label can not both be a Duplicate and Verified.")

        self.labels['A'].refresh_from_db()
        # Not changed
        self.assertEqual(self.labels['A'].duplicate, None)
