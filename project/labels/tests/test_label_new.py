from __future__ import unicode_literals

from django.core import mail
from django.shortcuts import resolve_url
from django.test import override_settings
from django.urls import reverse

from lib.tests.utils import (
    BasePermissionTest, ClientTest, sample_image_as_file)
from ..models import LabelGroup, Label


class PermissionTest(BasePermissionTest):

    @classmethod
    def setUpTestData(cls):
        super(PermissionTest, cls).setUpTestData()

        cls.labels = cls.create_labels(cls.user, ['A', 'B'], 'GroupA')

    def test_label_new(self):
        url = reverse('label_new')
        template = 'labels/label_new.html'

        self.assertPermissionLevel(
            url, self.SIGNED_IN, template=template,
            deny_type=self.REQUIRE_LOGIN)

    def test_label_new_ajax(self):
        url = reverse('label_new_ajax')

        self.assertPermissionLevel(
            url, self.SIGNED_IN, is_json=True, post_data={},
            deny_type=self.REQUIRE_LOGIN)


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
