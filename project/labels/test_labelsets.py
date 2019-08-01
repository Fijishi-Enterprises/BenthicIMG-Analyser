# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from backports import csv
from io import StringIO

from django.core.files.base import ContentFile
from django.shortcuts import resolve_url
from django.urls import reverse
from django.utils.html import escape

from lib.test_utils import BasePermissionTest, sample_image_as_file
from .models import Label
from .test_labels import LabelTest


class PermissionTest(BasePermissionTest):

    def test_labelset_add_private_source(self):
        url = resolve_url(
            'labelset_add', self.private_source.pk)
        self.assertPermissionDenied(url, None)
        self.assertPermissionDenied(url, self.user_outsider)
        self.assertPermissionDenied(url, self.user_viewer)
        self.assertPermissionDenied(url, self.user_editor)
        self.assertPermissionGranted(url, self.user_admin)

    def test_labelset_add_public_source(self):
        url = resolve_url(
            'labelset_add', self.public_source.pk)
        self.assertPermissionDenied(url, None)
        self.assertPermissionDenied(url, self.user_outsider)
        self.assertPermissionDenied(url, self.user_viewer)
        self.assertPermissionDenied(url, self.user_editor)
        self.assertPermissionGranted(url, self.user_admin)

    def test_labelset_edit_private_source(self):
        url = resolve_url(
            'labelset_edit', self.private_source.pk)
        self.assertPermissionDenied(url, None)
        self.assertPermissionDenied(url, self.user_outsider)
        self.assertPermissionDenied(url, self.user_viewer)
        self.assertPermissionDenied(url, self.user_editor)
        self.assertPermissionGranted(url, self.user_admin)

    def test_labelset_edit_public_source(self):
        url = resolve_url(
            'labelset_edit', self.public_source.pk)
        self.assertPermissionDenied(url, None)
        self.assertPermissionDenied(url, self.user_outsider)
        self.assertPermissionDenied(url, self.user_viewer)
        self.assertPermissionDenied(url, self.user_editor)
        self.assertPermissionGranted(url, self.user_admin)

    def test_labelset_import_private_source(self):
        url = resolve_url(
            'labelset_import', self.private_source.pk)
        self.assertPermissionDenied(url, None)
        self.assertPermissionDenied(url, self.user_outsider)
        self.assertPermissionDenied(url, self.user_viewer)
        self.assertPermissionDenied(url, self.user_editor)
        self.assertPermissionGranted(url, self.user_admin)

    def test_labelset_import_public_source(self):
        url = resolve_url(
            'labelset_import', self.public_source.pk)
        self.assertPermissionDenied(url, None)
        self.assertPermissionDenied(url, self.user_outsider)
        self.assertPermissionDenied(url, self.user_viewer)
        self.assertPermissionDenied(url, self.user_editor)
        self.assertPermissionGranted(url, self.user_admin)

    def test_labelset_import_preview_ajax_private_source(self):
        url = resolve_url(
            'labelset_import_preview_ajax', self.private_source.pk)
        self.assertPermissionDeniedAjax(url, None, post_data={})
        self.assertPermissionDeniedAjax(url, self.user_outsider, post_data={})
        self.assertPermissionDeniedAjax(url, self.user_viewer, post_data={})
        self.assertPermissionDeniedAjax(url, self.user_editor, post_data={})
        self.assertPermissionGrantedAjax(url, self.user_admin, post_data={})

    def test_labelset_import_preview_ajax_public_source(self):
        url = resolve_url(
            'labelset_import_preview_ajax', self.public_source.pk)
        self.assertPermissionDeniedAjax(url, None, post_data={})
        self.assertPermissionDeniedAjax(url, self.user_outsider, post_data={})
        self.assertPermissionDeniedAjax(url, self.user_viewer, post_data={})
        self.assertPermissionDeniedAjax(url, self.user_editor, post_data={})
        self.assertPermissionGrantedAjax(url, self.user_admin, post_data={})

    def test_labelset_import_ajax_private_source(self):
        url = resolve_url(
            'labelset_import_ajax', self.private_source.pk)
        self.assertPermissionDeniedAjax(url, None, post_data={})
        self.assertPermissionDeniedAjax(url, self.user_outsider, post_data={})
        self.assertPermissionDeniedAjax(url, self.user_viewer, post_data={})
        self.assertPermissionDeniedAjax(url, self.user_editor, post_data={})
        self.assertPermissionGrantedAjax(url, self.user_admin, post_data={})

    def test_labelset_import_ajax_public_source(self):
        url = resolve_url(
            'labelset_import_ajax', self.public_source.pk)
        self.assertPermissionDeniedAjax(url, None, post_data={})
        self.assertPermissionDeniedAjax(url, self.user_outsider, post_data={})
        self.assertPermissionDeniedAjax(url, self.user_viewer, post_data={})
        self.assertPermissionDeniedAjax(url, self.user_editor, post_data={})
        self.assertPermissionGrantedAjax(url, self.user_admin, post_data={})


class LabelsetCreateTest(LabelTest):
    """
    Test the new labelset page.
    """
    @classmethod
    def setUpTestData(cls):
        # Call the parent's setup (while still using this class as cls)
        super(LabelsetCreateTest, cls).setUpTestData()

        cls.user = cls.create_user()

        # Create source
        cls.source = cls.create_source(cls.user)

        # Create labels and group
        cls.group = cls.create_label_group("Group1")
        cls.create_label(cls.user, "Label A", 'A', cls.group)
        cls.create_label(cls.user, "Label B", 'B', cls.group)
        cls.create_label(cls.user, "Label C", 'C', cls.group)

        cls.url = reverse('labelset_add', args=[cls.source.pk])

    def test_success(self):
        """Successfully create a new labelset."""

        # These are the labels we'll try putting into the labelset.
        label_pks = [
            Label.objects.get(name=name).pk
            for name in ["Label A", "Label B"]
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


class LabelsetAddRemoveTest(LabelTest):
    """
    Test adding/removing labels from a labelset.
    """
    @classmethod
    def setUpTestData(cls):
        # Call the parent's setup (while still using this class as cls)
        super(LabelsetAddRemoveTest, cls).setUpTestData()

        cls.user = cls.create_user()

        # Create labels and group
        cls.group = cls.create_label_group("Group1")
        cls.create_label(cls.user, "Label A", 'A', cls.group)
        cls.create_label(cls.user, "Label B", 'B', cls.group)
        cls.create_label(cls.user, "Label C", 'C', cls.group)
        cls.create_label(cls.user, "Label D", 'D', cls.group)
        cls.create_label(cls.user, "Label E", 'E', cls.group)

        # Create source and labelset
        cls.source = cls.create_source(cls.user)
        cls.create_labelset(cls.user, cls.source, Label.objects.filter(
            default_code__in=['A', 'B', 'C']))

        cls.url = reverse('labelset_add', args=[cls.source.pk])

    def test_add(self):
        # Add D E
        label_pks = [
            Label.objects.get(default_code=default_code).pk
            for default_code in ['A', 'B', 'C', 'D', 'E']
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
        # Remove B C
        label_pks = [
            Label.objects.get(default_code=default_code).pk
            for default_code in ['A']
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
        # Remove A B, add D E
        label_pks = [
            Label.objects.get(default_code=default_code).pk
            for default_code in ['C', 'D', 'E']
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

    def test_cant_remove_label_with_annotations(self):
        # Annotate with C
        img = self.upload_image(self.user, self.source)
        self.add_annotations(self.user, img, {1: 'C'})

        # Remove C
        label_pks = [
            Label.objects.get(default_code=default_code).pk
            for default_code in ['A', 'B']
        ]
        self.client.force_login(self.user)
        response = self.client.post(
            self.url,
            dict(label_ids=','.join(str(pk) for pk in label_pks)),
            follow=True,
        )

        # Check for error message
        self.assertContains(response, escape(
            "The label 'Label C' is marked for removal from the"
            " labelset, but we can't remove it because the source"
            " still has annotations with this label."))

        # Check that the labelset changes didn't go through
        self.source.labelset.refresh_from_db()
        self.assertSetEqual(
            set(self.source.labelset.get_labels().values_list(
                'code', flat=True)),
            {'A', 'B', 'C'},
        )


class LabelsetImportBaseTest(LabelTest):

    def preview(self, csv_rows):
        stream = StringIO()
        writer = csv.writer(stream)
        for row in csv_rows:
            writer.writerow(row)

        return self.preview_raw(stream.getvalue())

    def preview_raw(self, csv_string):
        self.client.force_login(self.user)

        f = ContentFile(csv_string, name='A.csv')
        response = self.client.post(
            reverse('labelset_import_preview_ajax', args=[self.source.pk]),
            {'csv_file': f},
        )

        return response

    def assertPreviewTableRow(self, response_json, values):
        cells = ''.join(['<td>{v}</td>'.format(v=v) for v in values])
        self.assertInHTML(
            '<tr>' + cells + '</tr>',
            response_json['previewTable'])

    def assertError(self, response, error_message):
        self.assertEqual(response.json()['error'], error_message)

    def upload(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse('labelset_import_ajax', args=[self.source.pk]),
        )
        return response


class LabelsetImportCreateTest(LabelsetImportBaseTest):
    """
    Test adding/removing labels from a labelset.
    """
    @classmethod
    def setUpTestData(cls):
        # Call the parent's setup (while still using this class as cls)
        super(LabelsetImportCreateTest, cls).setUpTestData()

        cls.user = cls.create_user()

        # Create labels and group
        cls.group = cls.create_label_group("Group1")
        cls.labels = dict(
            A=cls.create_label(cls.user, "Label A", 'A', cls.group),
            B=cls.create_label(cls.user, "Label B", 'B', cls.group),
            C=cls.create_label(cls.user, "Label C", 'C', cls.group),
            D=cls.create_label(cls.user, "Label D", 'D', cls.group),
            E=cls.create_label(cls.user, "Label E", 'E', cls.group),
        )

        # Create source
        cls.source = cls.create_source(cls.user)

    def test_preview(self):
        csv_rows = [
            ['Label ID', 'Short code'],
            [self.labels['A'].pk, 'codeForA'],
            [self.labels['B'].pk, 'codeForB'],
        ]
        response = self.preview(csv_rows)
        response_json = response.json()

        self.assertEqual(response_json['success'], True)
        self.assertPreviewTableRow(
            response_json, [self.labels['A'].pk, "Label A", 'codeForA'])
        self.assertPreviewTableRow(
            response_json, [self.labels['B'].pk, "Label B", 'codeForB'])
        self.assertEqual(response_json['previewDetail'], "")

    def test_upload(self):
        csv_rows = [
            ['Label ID', 'Short code'],
            [self.labels['A'].pk, 'codeForA'],
            [self.labels['B'].pk, 'codeForB'],
        ]
        self.preview(csv_rows)
        self.upload()

        self.source.refresh_from_db()
        labels = self.source.labelset.get_labels()
        label_A = labels.get(global_label_id=self.labels['A'].pk)
        self.assertEqual(label_A.code, 'codeForA')
        label_B = labels.get(global_label_id=self.labels['B'].pk)
        self.assertEqual(label_B.code, 'codeForB')

    def test_missing_session_data(self):
        response = self.upload()
        self.assertError(
            response,
            "We couldn't find the expected data in your session."
            " Please try loading this page again. If the problem persists,"
            " contact a site admin.")

    def test_zero_data_rows(self):
        csv_rows = [
            ['Label ID', 'Short code'],
        ]
        response = self.preview(csv_rows)
        self.assertError(response, "No data rows found in the CSV.")

    def test_non_number_label_id(self):
        csv_rows = [
            ['Label ID', 'Short code'],
            ['abc', 'codeForA'],
        ]
        response = self.preview(csv_rows)
        self.assertError(response, "CSV has non-existent label id: abc")

    def test_nonexistent_label_id(self):
        csv_rows = [
            ['Label ID', 'Short code'],
            [0, 'codeForA'],
        ]
        response = self.preview(csv_rows)
        self.assertError(response, "CSV has non-existent label id: 0")

    def test_missing_required_column(self):
        csv_rows = [
            ['Short code'],
            ['codeForA'],
        ]
        response = self.preview(csv_rows)
        self.assertError(response, "CSV must have a column called Label ID")

    def test_column_header_different_case(self):
        csv_rows = [
            ['label id', 'SHORT Code'],
            [self.labels['A'].pk, 'codeForA'],
        ]
        self.preview(csv_rows)
        self.upload()
        self.source.refresh_from_db()
        self.assertIsNotNone(self.source.labelset)

    def test_columns_different_order(self):
        csv_rows = [
            ['Short code', 'Label ID'],
            ['codeForA', self.labels['A'].pk],
        ]
        self.preview(csv_rows)
        self.upload()
        self.source.refresh_from_db()
        self.assertIsNotNone(self.source.labelset)

    def test_unrecognized_columns(self):
        csv_rows = [
            ['Label ID', 'Short code', 'Other column 1', 'Other column 2'],
            [self.labels['A'].pk, 'codeForA', 'value 1', 'value 2'],
        ]
        self.preview(csv_rows)
        self.upload()
        self.source.refresh_from_db()
        self.assertIsNotNone(self.source.labelset)

    def test_missing_label_id(self):
        csv_rows = [
            ['Label ID', 'Short code'],
            [self.labels['A'].pk, 'codeForA'],
            ['', 'codeForB'],
        ]
        response = self.preview(csv_rows)
        self.assertError(response, "CSV row 3: Must have a value for Label ID")

    def test_missing_other_required_field(self):
        csv_rows = [
            ['Label ID', 'Short code'],
            [self.labels['A'].pk, ''],
            [self.labels['B'].pk, 'codeForB'],
        ]
        response = self.preview(csv_rows)
        self.assertError(
            response, "CSV row 2: Must have a value for Short code")

    def test_dupe_column(self):
        # Should end up accepting one of the dupe columns. In this event the
        # user probably screwed up, but no extra code is needed for us to
        # avoid a server error, and some more code is needed for us to detect
        # and report the situation. So we just let the user notice and deal
        # with the situation as needed.
        csv_rows = [
            ['Label ID', 'Short code', 'Short code'],
            [self.labels['A'].pk, 'codeForA', 'codeForB'],
        ]
        self.preview(csv_rows)
        self.upload()
        self.source.refresh_from_db()
        self.assertIsNotNone(self.source.labelset)

    def test_dupe_label_id(self):
        csv_rows = [
            ['Label ID', 'Short code'],
            [self.labels['A'].pk, 'codeForA'],
            [self.labels['A'].pk, 'code2'],
        ]
        response = self.preview(csv_rows)
        self.assertError(
            response, "More than one row with the same Label ID: {pk}".format(
                pk=self.labels['A'].pk))

    def test_code_conflict(self):
        csv_rows = [
            ['Label ID', 'Short code'],
            [self.labels['A'].pk, 'CODE1'],
            [self.labels['B'].pk, 'Code1'],
        ]
        response = self.preview(csv_rows)
        self.assertError(
            response,
            "The resulting labelset would have multiple labels with the code"
            " 'code1' (non case sensitive). This is not allowed.")

    def test_code_error(self):
        csv_rows = [
            ['Label ID', 'Short code'],
            [self.labels['A'].pk, '12345678901'],
            [self.labels['B'].pk, 'codeForB'],
        ]
        response = self.preview(csv_rows)
        self.assertError(
            response,
            "Row with id {pk} - Short Code: Ensure this value has at most"
            " 10 characters (it has 11).".format(pk=self.labels['A'].pk))


class LabelsetImportModifyTest(LabelsetImportBaseTest):
    """
    Test adding/removing labels from a labelset.
    """
    @classmethod
    def setUpTestData(cls):
        # Call the parent's setup (while still using this class as cls)
        super(LabelsetImportModifyTest, cls).setUpTestData()

        cls.user = cls.create_user()

        # Create labels and group
        cls.group = cls.create_label_group("Group1")
        cls.labels = dict(
            A=cls.create_label(cls.user, "Label A", 'A', cls.group),
            B=cls.create_label(cls.user, "Label B", 'B', cls.group),
            C=cls.create_label(cls.user, "Label C", 'C', cls.group),
            D=cls.create_label(cls.user, "Label D", 'D', cls.group),
            E=cls.create_label(cls.user, "Label E", 'E', cls.group),
        )

        # Create source and labelset
        cls.source = cls.create_source(cls.user)
        cls.create_labelset(cls.user, cls.source, Label.objects.filter(
            default_code__in=['A', 'B', 'C']))

        cls.url = reverse('labelset_add', args=[cls.source.pk])

    def test_create_entries(self):
        csv_rows = [
            ['Label ID', 'Short code'],
            [self.labels['D'].pk, 'codeForD'],
            [self.labels['E'].pk, 'codeForE'],
        ]
        self.preview(csv_rows)
        self.upload()

        self.source.refresh_from_db()
        labels = self.source.labelset.get_labels()
        labels.get(global_label_id=self.labels['A'].pk)
        labels.get(global_label_id=self.labels['B'].pk)
        labels.get(global_label_id=self.labels['C'].pk)
        label_D = labels.get(global_label_id=self.labels['D'].pk)
        self.assertEqual(label_D.code, 'codeForD')
        label_E = labels.get(global_label_id=self.labels['E'].pk)
        self.assertEqual(label_E.code, 'codeForE')

    def test_edit_existing_entries(self):
        csv_rows = [
            ['Label ID', 'Short code'],
            [self.labels['A'].pk, 'newCodeA'],
            [self.labels['B'].pk, 'newCodeB'],
        ]
        self.preview(csv_rows)
        self.upload()

        self.source.refresh_from_db()
        labels = self.source.labelset.get_labels()
        label_A = labels.get(global_label_id=self.labels['A'].pk)
        self.assertEqual(label_A.code, 'newCodeA')
        label_B = labels.get(global_label_id=self.labels['B'].pk)
        self.assertEqual(label_B.code, 'newCodeB')
        labels.get(global_label_id=self.labels['C'].pk)

    def test_create_and_edit(self):
        csv_rows = [
            ['Label ID', 'Short code'],
            [self.labels['A'].pk, 'newCodeA'],
            [self.labels['D'].pk, 'codeForD'],
        ]
        self.preview(csv_rows)
        self.upload()

        self.source.refresh_from_db()
        labels = self.source.labelset.get_labels()
        label_A = labels.get(global_label_id=self.labels['A'].pk)
        self.assertEqual(label_A.code, 'newCodeA')
        labels.get(global_label_id=self.labels['B'].pk)
        labels.get(global_label_id=self.labels['C'].pk)
        label_D = labels.get(global_label_id=self.labels['D'].pk)
        self.assertEqual(label_D.code, 'codeForD')

    def test_create_and_edit_preview(self):
        csv_rows = [
            ['Label ID', 'Short code'],
            [self.labels['A'].pk, 'newCodeA'],
            [self.labels['D'].pk, 'codeForD'],
        ]
        response = self.preview(csv_rows)
        response_json = response.json()

        self.assertEqual(response_json['success'], True)
        self.assertPreviewTableRow(
            response_json, [self.labels['A'].pk, "Label A", 'newCodeA'])
        self.assertPreviewTableRow(
            response_json, [self.labels['B'].pk, "Label B", 'B'])
        self.assertPreviewTableRow(
            response_json, [self.labels['C'].pk, "Label C", 'C'])
        self.assertPreviewTableRow(
            response_json, [self.labels['D'].pk, "Label D", 'codeForD'])
        self.assertEqual(response_json['previewDetail'], "")

    def test_code_conflict_with_existing_entry(self):
        csv_rows = [
            ['Label ID', 'Short code'],
            [self.labels['D'].pk, 'b'],
        ]
        response = self.preview(csv_rows)
        self.assertError(
            response,
            "The resulting labelset would have multiple labels with the code"
            " 'b' (non case sensitive). This is not allowed.")


class LabelsetImportFormatTest(LabelsetImportBaseTest):
    """
    File format/special character cases during labelset import.
    """
    @classmethod
    def setUpTestData(cls):
        # Call the parent's setup (while still using this class as cls)
        super(LabelsetImportFormatTest, cls).setUpTestData()

        cls.user = cls.create_user()

        # Create labels and group
        cls.group = cls.create_label_group("Group1")
        cls.labels = dict(
            A=cls.create_label(cls.user, "Label A", 'A', cls.group),
            B=cls.create_label(cls.user, "Label B", 'B', cls.group),
            C=cls.create_label(cls.user, "Label C", 'C', cls.group),
            D=cls.create_label(cls.user, "Label D", 'D', cls.group),
            E=cls.create_label(cls.user, "Label い", 'い', cls.group),
        )

        # Create source
        cls.source = cls.create_source(cls.user)

    def test_non_ascii(self):
        csv_content = (
            'Label ID,Short code'
            '\r\n{label_id},い'.format(label_id=self.labels['E'].pk)
        )
        self.preview_raw(csv_content)
        self.upload()
        self.source.refresh_from_db()
        self.assertIsNotNone(self.source.labelset)

    def test_crlf(self):
        csv_content = (
            'Label ID,Short code'
            '\r\n{label_id},A'.format(label_id=self.labels['A'].pk)
        )
        self.preview_raw(csv_content)
        self.upload()
        self.source.refresh_from_db()
        self.assertIsNotNone(self.source.labelset)

    def test_cr(self):
        csv_content = (
            'Label ID,Short code'
            '\r{label_id},A'.format(label_id=self.labels['A'].pk)
        )
        self.preview_raw(csv_content)
        self.upload()
        self.source.refresh_from_db()
        self.assertIsNotNone(self.source.labelset)

    def test_utf8_bom(self):
        csv_content = (
            '\ufeffLabel ID,Short code'
            '\n{label_id},A'.format(label_id=self.labels['A'].pk)
        )
        self.preview_raw(csv_content)
        self.upload()
        self.source.refresh_from_db()
        self.assertIsNotNone(self.source.labelset)

    def test_field_with_newline(self):
        csv_content = (
            'Label ID,Comments,Short code'
            '\n{label_id},"These are\nsome comments",A'.format(
                label_id=self.labels['A'].pk)
        )
        self.preview_raw(csv_content)
        self.upload()
        self.source.refresh_from_db()
        self.assertIsNotNone(self.source.labelset)

    def test_field_with_surrounding_quotes(self):
        csv_content = (
            'Label ID,Short code'
            '\n"{label_id}","A"'.format(
                label_id=self.labels['A'].pk)
        )
        self.preview_raw(csv_content)
        self.upload()
        self.source.refresh_from_db()
        self.assertIsNotNone(self.source.labelset)

    def test_field_with_surrounding_whitespace(self):
        csv_content = (
            'Label ID ,\tShort code\t'
            '\n\t{label_id} ,    A   '.format(
                label_id=self.labels['A'].pk)
        )
        self.preview_raw(csv_content)
        self.upload()
        self.source.refresh_from_db()
        self.assertIsNotNone(self.source.labelset)

    def test_non_csv(self):
        self.client.force_login(self.user)
        f = sample_image_as_file('A.jpg')
        response = self.client.post(
            reverse('labelset_import_preview_ajax', args=[self.source.pk]),
            {'csv_file': f},
        )
        self.assertError(response, "The selected file is not a CSV file.")

    def test_empty_file(self):
        response = self.preview_raw('')
        self.assertError(response, "The submitted file is empty.")


class LabelsetEditTest(LabelTest):
    """
    General tests for the view where you edit labelset entries (code etc.).
    """
    @classmethod
    def setUpTestData(cls):
        # Call the parent's setup (while still using this class as cls)
        super(LabelsetEditTest, cls).setUpTestData()

        cls.user = cls.create_user()

        # Create labels and group
        cls.group = cls.create_label_group("Group1")
        cls.labels = dict(
            A=cls.create_label(cls.user, "Label A", 'A', cls.group),
            B=cls.create_label(cls.user, "Label B", 'B', cls.group),
            C=cls.create_label(cls.user, "Label C", 'C', cls.group),
            D=cls.create_label(cls.user, "Label D", 'D', cls.group),
            E=cls.create_label(cls.user, "Label E", 'E', cls.group),
        )

        # Create source and labelset
        cls.source = cls.create_source(cls.user)
        cls.create_labelset(cls.user, cls.source, Label.objects.filter(
            default_code__in=['A', 'B']))

        cls.url = reverse('labelset_edit', args=[cls.source.pk])

    def test_success(self):
        labels = self.source.labelset.get_labels()
        post_data = {
            'form-TOTAL_FORMS': 2,
            'form-INITIAL_FORMS': 2,
            'form-MAX_NUM_FORMS': '',
            'form-0-id': labels.get(global_label_id=self.labels['A'].pk).pk,
            'form-0-code': 'newCodeA',
            'form-1-id': labels.get(global_label_id=self.labels['B'].pk).pk,
            'form-1-code': 'newCodeB',
        }

        self.client.force_login(self.user)
        self.client.post(self.url, post_data)

        self.source.labelset.refresh_from_db()
        labels = self.source.labelset.get_labels()
        label_A = labels.get(global_label_id=self.labels['A'].pk)
        self.assertEqual(label_A.code, 'newCodeA')
        label_B = labels.get(global_label_id=self.labels['B'].pk)
        self.assertEqual(label_B.code, 'newCodeB')

    def test_code_missing(self):
        labels = self.source.labelset.get_labels()
        post_data = {
            'form-TOTAL_FORMS': 2,
            'form-INITIAL_FORMS': 2,
            'form-MAX_NUM_FORMS': '',
            'form-0-id': labels.get(global_label_id=self.labels['A'].pk).pk,
            'form-0-code': 'newCodeA',
            'form-1-id': labels.get(global_label_id=self.labels['B'].pk).pk,
            'form-1-code': '',
        }

        self.client.force_login(self.user)
        response = self.client.post(self.url, post_data)

        self.assertContains(
            response,
            "Label B: Short Code: This field is required.")

    def test_code_error(self):
        labels = self.source.labelset.get_labels()
        post_data = {
            'form-TOTAL_FORMS': 2,
            'form-INITIAL_FORMS': 2,
            'form-MAX_NUM_FORMS': '',
            'form-0-id': labels.get(global_label_id=self.labels['A'].pk).pk,
            'form-0-code': 'newCodeATooLong',
            'form-1-id': labels.get(global_label_id=self.labels['B'].pk).pk,
            'form-1-code': 'newCodeA',
        }

        self.client.force_login(self.user)
        response = self.client.post(self.url, post_data)

        self.assertContains(
            response,
            "Label A: Short Code: Ensure this value has"
            " at most 10 characters (it has 15).")

    def test_code_conflict(self):
        labels = self.source.labelset.get_labels()
        post_data = {
            'form-TOTAL_FORMS': 2,
            'form-INITIAL_FORMS': 2,
            'form-MAX_NUM_FORMS': '',
            'form-0-id': labels.get(global_label_id=self.labels['A'].pk).pk,
            'form-0-code': 'newCodeA',
            'form-1-id': labels.get(global_label_id=self.labels['B'].pk).pk,
            'form-1-code': 'NEWCODEA',
        }

        self.client.force_login(self.user)
        response = self.client.post(self.url, post_data)

        self.assertContains(response, escape(
            "The resulting labelset would have multiple labels with the code"
            " 'newcodea' (non case sensitive). This is not allowed."))
