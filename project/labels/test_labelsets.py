import csv
from io import BytesIO

from django.core.files.base import ContentFile
from django.core.urlresolvers import reverse
from django.utils.html import escape

from images.models import Source
from labels.models import Label, LabelGroup
from lib.test_utils import ClientTest, sample_image_as_file


class LabelsetTest(ClientTest):

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
                # filename will be discarded, so it doesn't matter.
                thumbnail=sample_image_as_file('_.png'),
            )
        )
        cls.client.logout()

        return Label.objects.get(name=name)


class LabelsetAddPermissionTest(LabelsetTest):
    """
    Test the new labelset page.
    """
    @classmethod
    def setUpTestData(cls):
        # Call the parent's setup (while still using this class as cls)
        super(LabelsetAddPermissionTest, cls).setUpTestData()

        cls.user = cls.create_user()

        # Create source
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
        self.assertTemplateUsed(response, self.PERMISSION_DENIED_TEMPLATE)

    def test_load_page_as_source_viewer(self):
        """Don't have permission."""
        self.client.force_login(self.user_viewer)
        response = self.client.get(self.url)
        self.assertTemplateUsed(response, self.PERMISSION_DENIED_TEMPLATE)

    def test_load_page_as_source_editor(self):
        """Don't have permission."""
        self.client.force_login(self.user_editor)
        response = self.client.get(self.url)
        self.assertTemplateUsed(response, self.PERMISSION_DENIED_TEMPLATE)

    def test_load_page_as_source_admin(self):
        """Page loads normally."""
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        self.assertTemplateUsed(response, 'labels/labelset_add.html')


class LabelsetCreateTest(LabelsetTest):
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


class LabelsetAddRemoveTest(LabelsetTest):
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
        img = self.upload_image_new(self.user, self.source)
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


class LabelsetImportBaseTest(LabelsetTest):

    def preview(self, csv_rows):
        self.client.force_login(self.user)

        with BytesIO() as stream:
            writer = csv.writer(stream)
            for row in csv_rows:
                writer.writerow(row)

            f = ContentFile(stream.getvalue(), name='A.csv')
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

    def test_empty_file(self):
        csv_rows = []
        response = self.preview(csv_rows)
        self.assertError(response, "The submitted file is empty.")

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


class LabelsetEditTest(LabelsetTest):
    """
    Test adding/removing labels from a labelset.
    """
    @classmethod
    def setUpTestData(cls):
        # Call the parent's setup (while still using this class as cls)
        super(LabelsetEditTest, cls).setUpTestData()

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

    def test_success(self):
        # TODO
        pass

    def test_code_conflict(self):
        # TODO
        pass
