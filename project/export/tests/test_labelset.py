from django.core.files.base import ContentFile
from django.shortcuts import resolve_url
from django.urls import reverse

from export.tests.utils import BaseExportTest
from lib.tests.utils import BasePermissionTest
from labels.models import Label, LocalLabel
from labels.tests.utils import LabelTest


class PermissionTest(BasePermissionTest):

    def test_export_labelset(self):
        url = reverse('export_labelset', args=[self.source.pk])

        self.source_to_private()
        self.assertPermissionLevel(
            url, self.SOURCE_VIEW, content_type='text/csv')
        self.source_to_public()
        self.assertPermissionLevel(
            url, self.SIGNED_OUT, content_type='text/csv')


class GeneralTest(BaseExportTest, LabelTest):
    """
    General tests for the labelset-export-to-CSV view.
    """
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()

        cls.user = cls.create_user()
        cls.source = cls.create_source(cls.user)
        cls.export_url = resolve_url('export_labelset', cls.source.pk)

        # Create labels and group
        group = cls.create_label_group("Group")
        cls.labels = dict(
            A=cls.create_label(cls.user, "Label A", 'A', group),
            B=cls.create_label(cls.user, "Label B", 'B', group),
            C=cls.create_label(cls.user, "Label C", 'C', group),
        )

    def test_basic(self):
        # Create labelset
        self.create_labelset(self.user, self.source, Label.objects.filter(
            default_code__in=['A', 'C']))
        # Custom code
        local_c = LocalLabel.objects.get(
            labelset=self.source.labelset, code='C')
        local_c.code = 'Coral'
        local_c.save()

        # Export and check
        response = self.client.get(self.export_url)
        expected_lines = [
            'Label ID,Short Code',
            '{id_A},A'.format(id_A=self.labels['A'].pk),
            '{id_C},Coral'.format(id_C=self.labels['C'].pk),
        ]
        self.assert_csv_content_equal(response.content, expected_lines)

    def test_unicode(self):
        """Test that non-ASCII characters don't cause issues."""
        # Create labelset
        self.create_labelset(self.user, self.source, Label.objects.filter(
            default_code__in=['A']))
        # Set custom code
        local_a = LocalLabel.objects.get(
            labelset=self.source.labelset, code='A')
        local_a.code = 'あ'
        local_a.save()

        # Export
        response = self.client.get(self.export_url)

        # Check
        expected_lines = ([
            'Label ID,Short Code',
            '{id_A},あ'.format(id_A=self.labels['A'].pk),
        ])
        self.assert_csv_content_equal(response.content, expected_lines)

    def test_rows_sorted_by_locallabel_code(self):
        """
        Test that exported CSV rows are sorted by LocalLabel code, not
        by name or default code.
        """
        # Create labelset
        self.create_labelset(self.user, self.source, Label.objects.filter(
            default_code__in=['A', 'B', 'C']))
        # Custom codes; ordering by these codes gives a different order from
        # ordering by name or default code
        local_a = LocalLabel.objects.get(
            labelset=self.source.labelset, code='A')
        local_a.code = '2'
        local_a.save()
        local_b = LocalLabel.objects.get(
            labelset=self.source.labelset, code='B')
        local_b.code = '1'
        local_b.save()
        local_c = LocalLabel.objects.get(
            labelset=self.source.labelset, code='C')
        local_c.code = '3'
        local_c.save()

        # Export
        response = self.client.get(self.export_url)

        # Check
        expected_lines = ([
            'Label ID,Short Code',
            '{id_B},1'.format(id_B=self.labels['B'].pk),
            '{id_A},2'.format(id_A=self.labels['A'].pk),
            '{id_C},3'.format(id_C=self.labels['C'].pk),
        ])
        self.assert_csv_content_equal(response.content, expected_lines)

    def test_upload_and_export(self):
        """Test that we can upload a labelset CSV and then export the same
        CSV."""
        # Upload labelset
        content = ''
        csv_lines = [
            'Label ID,Short Code',
            '{id_A},A'.format(id_A=self.labels['A'].pk),
            '{id_C},Coral'.format(id_C=self.labels['C'].pk),
        ]
        for line in csv_lines:
            content += (line + '\n')
        csv_file = ContentFile(content, name='labelset.csv')

        self.client.force_login(self.user)
        self.client.post(
            resolve_url('labelset_import_preview_ajax', self.source.pk),
            {'csv_file': csv_file},
        )
        self.client.post(
            resolve_url('labelset_import_ajax', self.source.pk),
        )

        # Export and check
        response = self.client.get(self.export_url)
        self.assert_csv_content_equal(response.content, csv_lines)
