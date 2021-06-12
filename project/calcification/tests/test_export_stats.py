from django.urls import reverse

from export.tests.utils import BaseExportTest
from lib.tests.utils import BasePermissionTest, ClientTest
from .utils import create_default_calcify_table


class PermissionTest(BasePermissionTest):

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()

        cls.labels = cls.create_labels(cls.user, ['A', 'B'], 'GroupA')
        cls.create_labelset(cls.user, cls.source, cls.labels)

        cls.calcify_table = create_default_calcify_table('Atlantic', dict())

    def test_calcify_stats_export(self):
        get_params = dict(rate_table_id=self.calcify_table.pk)
        url = self.make_url_with_params(
            reverse('calcification:stats_export', args=[self.source.pk]),
            get_params)

        self.source_to_private()
        self.assertPermissionLevel(
            url, self.SOURCE_VIEW, content_type='text/csv')
        self.source_to_public()
        self.assertPermissionLevel(
            url, self.SIGNED_IN, content_type='text/csv',
            deny_type=self.REQUIRE_LOGIN)


class BaseCalcifyStatsExportTest(BaseExportTest):
    """Subclasses must define self.client and self.source."""

    def export_calcify_stats(self, data):
        """GET the export view and return the response."""
        self.client.force_login(self.user)
        return self.client.get(
            reverse('calcification:stats_export', args=[self.source.pk]),
            data, follow=True)


class ExportTest(BaseCalcifyStatsExportTest):

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()

        cls.user = cls.create_user()
        cls.source = cls.create_source(
            cls.user, name="Test source", simple_number_of_points=5)

        cls.labels = cls.create_labels(
            cls.user, ['A', 'B', 'C'], 'GroupA')
        cls.create_labelset(cls.user, cls.source, cls.labels)
        cls.label_pks = {label.name: label.pk for label in cls.labels}

    def test_filename_and_content_type(self):
        calcify_table = create_default_calcify_table('Atlantic', {})
        response = self.export_calcify_stats(
            dict(rate_table_id=calcify_table.pk))

        # TODO: Also test for the correct date in the filename, perhaps
        # allowing for being 1 day off so the test is robust
        self.assertTrue(
            response['content-disposition'].startswith(
                'attachment;filename="Test source - Calcification rates - '),
            msg="Filename should have the source name as expected")
        self.assertTrue(
            response['content-disposition'].endswith('.csv"'))

        self.assertTrue(
            response['content-type'].startswith('text/csv'),
            msg="Content type should be CSV")

    def test_basic_contents(self):
        img1 = self.upload_image(
            self.user, self.source, dict(filename='1.jpg'))
        self.add_annotations(self.user, img1, {
            1: 'A', 2: 'A', 3: 'A', 4: 'A', 5: 'A'})

        img2 = self.upload_image(
            self.user, self.source, dict(filename='2.jpg'))
        self.add_annotations(self.user, img2, {
            1: 'A', 2: 'B', 3: 'A', 4: 'B', 5: 'A'})

        calcify_table = create_default_calcify_table(
            'Atlantic',
            {
                self.label_pks['A']: dict(
                    mean=4.0, lower_bound=3.2, upper_bound=4.8),
                self.label_pks['B']: dict(
                    mean=1.0, lower_bound=0.8, upper_bound=1.3),
            },
        )

        response = self.export_calcify_stats(
            dict(rate_table_id=calcify_table.pk))

        # Column headers, image IDs/names, calculations, and decimal places
        # should be as expected; and should work with multiple images
        expected_lines = [
            'Image ID,Image name,Mean rate,Lower bound,Upper bound',
            f'{img1.pk},1.jpg,4.000,3.200,4.800',
            # 4.0*0.6 + 1.0*0.4
            # 3.2*0.6 + 0.8*0.4
            # 4.8*0.6 + 1.3*0.4
            f'{img2.pk},2.jpg,2.800,2.240,3.400',
        ]
        self.assert_csv_content_equal(response.content, expected_lines)

    def test_zero_for_undefined_rate(self):
        """If a label has no rate defined for it, should assume a 0 rate."""
        img1 = self.upload_image(
            self.user, self.source, dict(filename='1.jpg'))
        self.add_annotations(self.user, img1, {
            1: 'A', 2: 'B', 3: 'A', 4: 'B', 5: 'A'})

        calcify_table = create_default_calcify_table(
            'Atlantic',
            {
                self.label_pks['A']: dict(
                    mean=4.0, lower_bound=3.2, upper_bound=4.8),
                # Nothing for B
            },
        )

        response = self.export_calcify_stats(
            dict(rate_table_id=calcify_table.pk))

        expected_lines = [
            'Image ID,Image name,Mean rate,Lower bound,Upper bound',
            # 4.0*0.6
            # 3.2*0.6
            # 4.8*0.6
            f'{img1.pk},1.jpg,2.400,1.920,2.880',
        ]
        self.assert_csv_content_equal(response.content, expected_lines)

    def test_different_tables(self):
        """Rate table choice should be respected in the export."""
        img1 = self.upload_image(
            self.user, self.source, dict(filename='1.jpg'))
        self.add_annotations(self.user, img1, {
            1: 'A', 2: 'B', 3: 'C', 4: 'B', 5: 'C'})

        calcify_table_1 = create_default_calcify_table(
            'Atlantic',
            {
                self.label_pks['A']: dict(
                    mean=4.0, lower_bound=3.2, upper_bound=4.8),
                self.label_pks['B']: dict(
                    mean=1.0, lower_bound=0.8, upper_bound=1.3),
            },
        )
        calcify_table_2 = create_default_calcify_table(
            'Indo-Pacific',
            {
                self.label_pks['B']: dict(
                    mean=1.5, lower_bound=1.0, upper_bound=2.0),
                self.label_pks['C']: dict(
                    mean=-3.0, lower_bound=-4.2, upper_bound=-2.2),
            },
        )

        # Table 1
        response = self.export_calcify_stats(
            dict(rate_table_id=calcify_table_1.pk))
        expected_lines = [
            'Image ID,Image name,Mean rate,Lower bound,Upper bound',
            # 4.0*0.2 + 1.0*0.4
            # 3.2*0.2 + 0.8*0.4
            # 4.8*0.2 + 1.3*0.4
            f'{img1.pk},1.jpg,1.200,0.960,1.480',
        ]
        self.assert_csv_content_equal(response.content, expected_lines)

        # Table 2
        response = self.export_calcify_stats(
            dict(rate_table_id=calcify_table_2.pk))
        expected_lines = [
            'Image ID,Image name,Mean rate,Lower bound,Upper bound',
            # 1.5*0.4 + -3.0*0.4
            # 1.0*0.4 + -4.2*0.4
            # 2.0*0.4 + -2.2*0.4
            f'{img1.pk},1.jpg,-0.600,-1.280,-0.080',
        ]
        self.assert_csv_content_equal(response.content, expected_lines)

    def test_optional_columns_contributions(self):
        """Test the optional mean and bounds contributions columns."""
        img1 = self.upload_image(
            self.user, self.source, dict(filename='1.jpg'))
        self.add_annotations(self.user, img1, {
            1: 'A', 2: 'B', 3: 'A', 4: 'B', 5: 'A'})

        calcify_table = create_default_calcify_table(
            'Atlantic',
            {
                self.label_pks['A']: dict(
                    mean=4.0, lower_bound=3.2, upper_bound=4.8),
                self.label_pks['B']: dict(
                    mean=1.0, lower_bound=0.8, upper_bound=1.3),
            },
        )

        # Mean only
        response = self.export_calcify_stats(
            dict(
                rate_table_id=calcify_table.pk,
                optional_columns='per_label_mean'))
        expected_lines = [
            'Image ID,Image name,Mean rate,Lower bound,Upper bound,'
            'A M,B M,C M',
            # 4.0*0.6 + 1.0*0.4
            # 3.2*0.6 + 0.8*0.4
            # 4.8*0.6 + 1.3*0.4
            f'{img1.pk},1.jpg,2.800,2.240,3.400,'
            # 4.0*0.6
            # 1.0*0.4
            # 0
            '2.400,0.400,0.000',
        ]
        self.assert_csv_content_equal(response.content, expected_lines)

        # Bounds only
        response = self.export_calcify_stats(
            dict(
                rate_table_id=calcify_table.pk,
                optional_columns='per_label_bounds'))
        expected_lines = [
            'Image ID,Image name,Mean rate,Lower bound,Upper bound,'
            'A LB,B LB,C LB,A UB,B UB,C UB',
            f'{img1.pk},1.jpg,2.800,2.240,3.400,'
            # 3.2*0.6
            # 0.8*0.4
            # 0
            # 4.8*0.6
            # 1.3*0.4
            # 0
            '1.920,0.320,0.000,2.880,0.520,0.000',
        ]
        self.assert_csv_content_equal(response.content, expected_lines)

        # Mean and bounds
        response = self.export_calcify_stats(
            dict(
                rate_table_id=calcify_table.pk,
                optional_columns=['per_label_mean', 'per_label_bounds']))
        expected_lines = [
            'Image ID,Image name,Mean rate,Lower bound,Upper bound,'
            'A M,B M,C M,A LB,B LB,C LB,A UB,B UB,C UB',
            f'{img1.pk},1.jpg,2.800,2.240,3.400,'
            '2.400,0.400,0.000,1.920,0.320,0.000,2.880,0.520,0.000',
        ]
        self.assert_csv_content_equal(response.content, expected_lines)

    def test_no_negative_zero(self):
        """
        Should not show -0.000 for zero contributions on labels with
        negative rates.
        """
        img1 = self.upload_image(
            self.user, self.source, dict(filename='1.jpg'))
        self.add_annotations(self.user, img1, {
            1: 'A', 2: 'A', 3: 'A', 4: 'A', 5: 'A'})

        calcify_table = create_default_calcify_table(
            'Atlantic',
            {
                self.label_pks['A']: dict(
                    mean=4.0, lower_bound=3.2, upper_bound=4.8),
                self.label_pks['C']: dict(
                    mean=-3.0, lower_bound=-4.2, upper_bound=-2.2),
            },
        )

        # Mean only
        response = self.export_calcify_stats(
            dict(
                rate_table_id=calcify_table.pk,
                optional_columns=['per_label_mean', 'per_label_bounds']))
        expected_lines = [
            'Image ID,Image name,Mean rate,Lower bound,Upper bound,'
            'A M,B M,C M,A LB,B LB,C LB,A UB,B UB,C UB',
            f'{img1.pk},1.jpg,4.000,3.200,4.800,'
            # Contributions from C in particular should be 0.000, not -0.000
            '4.000,0.000,0.000,3.200,0.000,0.000,4.800,0.000,0.000',
        ]
        self.assert_csv_content_equal(response.content, expected_lines)

    def test_nonexistent_table_id(self):
        """
        Nonexistent table ID should return to Browse with an error message at
        the top.
        """
        # No tables should have been created yet, so this ID should be
        # nonexistent.
        response = self.export_calcify_stats(
            dict(rate_table_id=1))

        # Display an error in HTML instead of serving CSV.
        self.assertTrue(response['content-type'].startswith('text/html'))
        # It's not the most intuitive error message, but it shouldn't be a
        # common error case either (e.g. people typing URLs with GET params
        # manually).
        self.assertContains(
            response,
            "Label rates to use: Select a valid choice."
            " 1 is not one of the available choices.")

    # TODO: Test ID of a table belonging to another source.


class ImageSetTest(BaseCalcifyStatsExportTest):
    """
    Test calcification stats export to CSV for different kinds of image
    subsets.
    """
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()

        cls.user = cls.create_user()
        cls.source = cls.create_source(
            cls.user, simple_number_of_points=5)
        cls.labels = cls.create_labels(cls.user, ['A', 'B'], 'GroupA')
        cls.create_labelset(cls.user, cls.source, cls.labels)

        cls.calcify_table = create_default_calcify_table('Atlantic', dict())

    def assert_csv_image_set(self, actual_csv_content, expected_images):
        # Convert from bytes to Unicode if necessary.
        if isinstance(actual_csv_content, bytes):
            actual_csv_content = actual_csv_content.decode()

        # The Python csv module uses \r\n by default (as part of the Excel
        # dialect). Due to the way we compare line by line, splitting on
        # \n would mess up the comparison, so we use split() instead of
        # splitlines().
        actual_lines = actual_csv_content.split('\r\n')
        # Since we're not using splitlines(), we have to deal with ending
        # newlines manually.
        if actual_lines[-1] == "":
            actual_lines.pop()

        # expected_images should be an iterable of Image objects. We'll check
        # that expected_images are exactly the images represented in line 2
        # of the CSV onward.
        self.assertEqual(
            len(expected_images), len(actual_lines)-1,
            msg="Number of images in the CSV should be as expected")

        for line, image in zip(actual_lines[1:], expected_images):
            self.assertTrue(
                line.startswith(f'{image.pk},{image.metadata.name},'),
                msg="CSV line should have the expected image ID and name")

    def test_all_images_single(self):
        """Export for 1 out of 1 images."""
        img1 = self.upload_image(
            self.user, self.source, dict(filename='1.jpg'))

        response = self.export_calcify_stats(
            dict(rate_table_id=self.calcify_table.pk))
        self.assert_csv_image_set(response.content, [img1])

    def test_all_images_multiple(self):
        """Export for n out of n images."""
        img1 = self.upload_image(
            self.user, self.source, dict(filename='1.jpg'))
        img2 = self.upload_image(
            self.user, self.source, dict(filename='2.jpg'))
        img3 = self.upload_image(
            self.user, self.source, dict(filename='3.jpg'))

        response = self.export_calcify_stats(
            dict(rate_table_id=self.calcify_table.pk))
        self.assert_csv_image_set(response.content, [img1, img2, img3])

    def test_image_subset_by_metadata(self):
        """Export for some, but not all, images."""
        img1 = self.upload_image(
            self.user, self.source, dict(filename='1.jpg'))
        img2 = self.upload_image(
            self.user, self.source, dict(filename='2.jpg'))
        img3 = self.upload_image(
            self.user, self.source, dict(filename='3.jpg'))
        img1.metadata.aux1 = 'X'
        img1.metadata.save()
        img2.metadata.aux1 = 'Y'
        img2.metadata.save()
        img3.metadata.aux1 = 'X'
        img3.metadata.save()

        data = self.default_search_params.copy()
        data['aux1'] = 'X'
        data['rate_table_id'] = self.calcify_table.pk
        response = self.export_calcify_stats(data)
        self.assert_csv_image_set(response.content, [img1, img3])

    def test_image_empty_set(self):
        """Export for 0 images."""
        self.upload_image(
            self.user, self.source, dict(filename='1.jpg'))

        data = self.default_search_params.copy()
        data['image_name'] = '5.jpg'
        data['rate_table_id'] = self.calcify_table.pk
        response = self.export_calcify_stats(data)
        self.assert_csv_image_set(response.content, [])

    def test_invalid_image_set_params(self):
        self.upload_image(self.user, self.source)

        data = self.default_search_params.copy()
        data['photo_date_0'] = 'abc'
        data['rate_table_id'] = self.calcify_table.pk
        response = self.export_calcify_stats(data)

        # Display an error in HTML instead of serving CSV.
        self.assertTrue(response['content-type'].startswith('text/html'))
        self.assertContains(response, "Image-search parameters were invalid.")

    def test_dont_get_other_sources_images(self):
        """Don't export for other sources' images."""
        img1 = self.upload_image(
            self.user, self.source, dict(filename='1.jpg'))

        source2 = self.create_source(self.user, simple_number_of_points=5)
        self.create_labelset(self.user, source2, self.labels)
        self.upload_image(self.user, source2, dict(filename='2.jpg'))

        response = self.export_calcify_stats(
            dict(rate_table_id=self.calcify_table.pk))
        # Should have image 1, but not 2
        self.assert_csv_image_set(response.content, [img1])


class UnicodeTest(BaseCalcifyStatsExportTest):
    """Test that non-ASCII characters don't cause problems."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()

        cls.user = cls.create_user()
        cls.source = cls.create_source(
            cls.user, simple_number_of_points=5)

        # No Unicode to test on labels, since the export uses the label name,
        # which is ASCII only.
        labels = cls.create_labels(cls.user, ['A'], 'GroupA')
        cls.create_labelset(cls.user, cls.source, labels)

        cls.calcify_table = create_default_calcify_table('Atlantic', dict())

    def test(self):
        img1 = self.upload_image(
            self.user, self.source, dict(filename='あ.jpg'))

        response = self.export_calcify_stats(
            dict(rate_table_id=self.calcify_table.pk))
        expected_lines = [
            'Image ID,Image name,Mean rate,Lower bound,Upper bound',
            f'{img1.pk},あ.jpg,0.000,0.000,0.000',
        ]
        self.assert_csv_content_equal(response.content, expected_lines)


class BrowseActionsTest(ClientTest):

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()

        cls.user = cls.create_user()
        cls.source = cls.create_source(cls.user)
        group1_labels = cls.create_labels(
            cls.user, ['A', 'B', 'C', 'D', 'E', 'F'], 'Group1')
        cls.create_labels(cls.user, ['G', 'H'], 'Group2')

        # Create a labelset with only a subset of the labels (6 of 8)
        cls.create_labelset(cls.user, cls.source, group1_labels)

    # TODO
