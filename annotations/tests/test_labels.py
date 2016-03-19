import os

from django.conf import settings
from django.core.urlresolvers import reverse
from django.db.models import Count

from annotations.models import Label, LabelGroup, LabelSet
from images.models import Source
from lib.test_utils import ClientTest, MediaTestComponent

class LabelListTest(ClientTest):
    """
    Test the label list page.
    """

    def test_load_page(self):
        """Load the page."""
        response = self.client.get(reverse('label_list'))
        self.assertStatusOK(response)

class LabelDetailTest(ClientTest):
    """
    Test the label detail page.
    """
    fixtures = ['test_labels.yaml']

    def test_load_page(self):
        """Load the page."""
        response = self.client.get(
            reverse('label_main', kwargs=dict(
                label_id=Label.objects.get(code='Scarlet').pk
            ))
        )
        self.assertStatusOK(response)

class NewLabelTest(ClientTest):
    """
    As long as the new label page still exists, at least check that it
    doesn't let in anonymous users.
    """

    def test_load_page_anonymous(self):
        """Load the page while logged out -> sign-in prompt."""
        response = self.client.get(reverse('label_new'))
        self.assertRedirects(
            response,
            reverse('signin')+'?next='+reverse('label_new'),
        )

class NewLabelsetTest(ClientTest):
    """
    Test the new labelset page.
    """
    extra_components = [MediaTestComponent]
    fixtures = ['test_users.yaml', 'test_sources.yaml', 'test_labels.yaml']
    source_member_roles = [
        ('public1', 'user3', Source.PermTypes.EDIT.code),
        ('public1', 'user4', Source.PermTypes.ADMIN.code),
    ]

    def test_load_page_anonymous(self):
        """
        Load the page while logged out ->
        sorry, don't have permission.
        """
        url = reverse('labelset_new', kwargs=dict(
            source_id=Source.objects.get(name='public1').pk
        ))
        response = self.client.get(url)
        self.assertStatusOK(response)
        self.assertTemplateUsed(response, self.PERMISSION_DENIED_TEMPLATE)

    def test_load_page_as_source_outsider(self):
        """
        Load the page as a user outside the source ->
        sorry, don't have permission.
        """
        self.client.login(username='user2', password='secret')

        url = reverse('labelset_new', kwargs=dict(
            source_id=Source.objects.get(name='public1').pk
        ))
        response = self.client.get(url)
        self.assertStatusOK(response)
        self.assertTemplateUsed(response, self.PERMISSION_DENIED_TEMPLATE)

    def test_load_page_as_source_editor(self):
        """
        Load the page as a source editor ->
        sorry, don't have permission.
        """
        self.client.login(username='user3', password='secret')

        url = reverse('labelset_new', kwargs=dict(
            source_id=Source.objects.get(name='public1').pk
        ))
        response = self.client.get(url)
        self.assertStatusOK(response)
        self.assertTemplateUsed(response, self.PERMISSION_DENIED_TEMPLATE)

    def test_load_page_as_source_admin(self):
        """
        Load the page as a source admin -> page loads normally.
        """
        self.client.login(username='user4', password='secret')

        url = reverse('labelset_new', kwargs=dict(
            source_id=Source.objects.get(name='public1').pk
        ))
        response = self.client.get(url)
        self.assertStatusOK(response)
        self.assertTemplateUsed(response, 'annotations/labelset_new.html')

    def test_label_creation(self):
        """Successfully create a new label."""
        self.client.login(username='user4', password='secret')

        url = reverse('labelset_new', kwargs=dict(
            source_id=Source.objects.get(name='public1').pk
        ))
        sample_uploadable_directory = os.path.join(settings.SAMPLE_UPLOADABLES_ROOT, 'data')
        thumbnail_path = os.path.join(sample_uploadable_directory, '001_2012-05-01_color-grid-001.png')

        with open(thumbnail_path, 'rb') as thumbnail:
            response = self.client.post(
                url,
                dict(
                    # create_label triggers the new-label form.
                    # The key just needs to be there in the POST;
                    # the value doesn't matter.
                    create_label='.',
                    name="Vermilion",
                    code='Verm',
                    group=LabelGroup.objects.get(code="Red").pk,
                    description="A red-orange hue.",
                    thumbnail=thumbnail,
                )
            )

        self.assertStatusOK(response)

        # Check that the label was created, and has the expected field values
        label = Label.objects.get(name="Vermilion")
        self.assertEqual(label.code, 'Verm')
        self.assertEqual(label.group.code, "Red")
        self.assertEqual(label.description, "A red-orange hue.")

        # TODO: Test that the thumbnail seems correct

    def test_labelset_creation(self):
        """Successfully create a new labelset."""
        self.client.login(username='user4', password='secret')

        source_pk = Source.objects.get(name='public1').pk
        url = reverse('labelset_new', kwargs=dict(
            source_id=source_pk
        ))
        # These are the labels we'll try putting into the labelset.
        label_pks = [
            Label.objects.get(code=code).pk
            for code in ['UMarine', 'Forest']
        ]

        response = self.client.post(
            url,
            dict(
                # create_labelset indicates that the new-labelset form should
                # be used, not the new-label form which is also on the page.
                # The key just needs to be there in the POST;
                # the value doesn't matter.
                create_labelset='.',
                labels=label_pks,
            ),
            follow=True,
        )

        url = reverse('labelset_main', kwargs=dict(
            source_id=source_pk,
        ))
        self.assertRedirects(response, url)

        # Check the new labelset for the expected labels.
        labelset = Source.objects.get(pk=source_pk).labelset
        self.assertListEqual(
            [label.code for label in labelset.labels.all()],
            ['UMarine', 'Forest'],
        )

class EditLabelsetTest(ClientTest):
    """
    Test the edit labelset page.
    """
    fixtures = [
        'test_users.yaml', 'test_sources.yaml',
        'test_labels.yaml', 'test_labelsets.yaml',
    ]
    source_member_roles = [
        ('public1', 'user3', Source.PermTypes.EDIT.code),
        ('public1', 'user4', Source.PermTypes.ADMIN.code),
    ]

    def test_load_page_anonymous(self):
        """
        Load the page while logged out ->
        sorry, don't have permission.
        """
        url = reverse('labelset_edit', kwargs=dict(
            source_id=Source.objects.get(name='public1').pk
        ))
        response = self.client.get(url)
        self.assertStatusOK(response)
        self.assertTemplateUsed(response, self.PERMISSION_DENIED_TEMPLATE)

    def test_load_page_as_source_outsider(self):
        """
        Load the page as a user outside the source ->
        sorry, don't have permission.
        """
        self.client.login(username='user2', password='secret')

        url = reverse('labelset_edit', kwargs=dict(
            source_id=Source.objects.get(name='public1').pk
        ))
        response = self.client.get(url)
        self.assertStatusOK(response)
        self.assertTemplateUsed(response, self.PERMISSION_DENIED_TEMPLATE)

    def test_load_page_as_source_editor(self):
        """
        Load the page as a source editor ->
        sorry, don't have permission.
        """
        self.client.login(username='user3', password='secret')

        url = reverse('labelset_edit', kwargs=dict(
            source_id=Source.objects.get(name='public1').pk
        ))
        response = self.client.get(url)
        self.assertStatusOK(response)
        self.assertTemplateUsed(response, self.PERMISSION_DENIED_TEMPLATE)

    def test_load_page_with_no_labelset(self):
        """
        Load the page as a source admin, but with no labelset on the source ->
        redirect to new labelset page.
        """
        self.client.login(username='user4', password='secret')

        edit_url = reverse('labelset_edit', kwargs=dict(
            source_id=Source.objects.get(name='public1').pk
        ))
        new_url = reverse('labelset_new', kwargs=dict(
            source_id=Source.objects.get(name='public1').pk
        ))
        response = self.client.get(edit_url)
        self.assertRedirects(response, new_url)

    def test_load_page_with_labelset(self):
        """
        Load the page as a source admin, with a labelset on the source ->
        page loads normally.
        """
        # Ensure our source has a non-empty labelset.
        # Here we query for labelsets with more than 0 labels.
        # Source: http://stackoverflow.com/a/5080597/
        labelsets = LabelSet.objects.annotate(num_labels=Count('labels'))
        a_non_empty_labelset = labelsets.filter(num_labels__gt=0)[0]
        source = Source.objects.get(name='public1')
        source.labelset = a_non_empty_labelset
        source.save()

        self.client.login(username='user4', password='secret')

        url = reverse('labelset_edit', kwargs=dict(
            source_id=Source.objects.get(name='public1').pk
        ))
        response = self.client.get(url)
        self.assertStatusOK(response)
        self.assertTemplateUsed(response, 'annotations/labelset_edit.html')

    def test_edit_success(self):
        """
        Edit the labelset successfully.
        """
        # Ensure our source has a non-empty labelset.
        # Here we query for labelsets with more than 0 labels.
        # Source: http://stackoverflow.com/a/5080597/
        labelsets = LabelSet.objects.annotate(num_labels=Count('labels'))
        a_non_empty_labelset = labelsets.filter(num_labels__gt=0)[0]
        source = Source.objects.get(name='public1')
        source.labelset = a_non_empty_labelset
        source.save()

        self.client.login(username='user4', password='secret')

        edit_url = reverse('labelset_edit', kwargs=dict(
            source_id=Source.objects.get(name='public1').pk
        ))
        detail_url = reverse('labelset_main', kwargs=dict(
            source_id=Source.objects.get(name='public1').pk
        ))
        label_pks = [
            Label.objects.get(code=code).pk
            for code in ['UMarine', 'Forest']
        ]

        response = self.client.post(
            edit_url,
            # edit_labelset indicates that the edit-labelset form should
            # be used, not the new-label form which is also on the page.
            # The key just needs to be there in the POST;
            # the value doesn't matter.
            dict(edit_labelset='.', labels=label_pks),
        )

        # Should redirect to the labelset viewing page.
        self.assertRedirects(response, detail_url)

        # Check the edited labelset for the expected labels.
        labelset = Source.objects.get(pk=source.pk).labelset
        self.assertListEqual(
            [label.code for label in labelset.labels.all()],
            ['UMarine', 'Forest'],
        )

    # TODO: Check that the new label form works.
    # TODO: Check that the cancel button works.