from bs4 import BeautifulSoup
from django.urls import reverse
from django.utils.html import escape as html_escape

from calcification.tests.utils import create_default_calcify_table
from images.model_utils import PointGen
from images.models import Source
from lib.tests.utils import (
    BasePermissionTest, ClientTest, sample_image_as_file)
from ..models import LabelGroup, Label
from ..templatetags.labels import (
    popularity_bar as popularity_bar_tag, status_icon as status_icon_tag)


class PermissionTest(BasePermissionTest):

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()

        cls.labels = cls.create_labels(cls.user, ['A', 'B'], 'GroupA')

    def test_label_main(self):
        url = reverse('label_main', args=[self.labels[0].pk])
        template = 'labels/label_main.html'

        self.assertPermissionLevel(url, self.SIGNED_OUT, template=template)

    def test_label_example_patches_ajax(self):
        url = reverse('label_example_patches_ajax', args=[self.labels[0].pk])

        self.assertPermissionLevel(url, self.SIGNED_OUT, is_json=True)


class LabelMainTest(ClientTest):
    """
    Test the label detail page.
    """
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()

        cls.user = cls.create_user()

        cls.group = LabelGroup(name="Group 1", code='G1')
        cls.group.save()

    def test_basic_fields(self):
        label = Label(
            name="Label A",
            default_code='A',
            group=self.group,
            description="This is a\nmultiline description.",
            # This filename will be discarded in favor of a generated one.
            thumbnail=sample_image_as_file('_.png'),
            created_by=self.user,
        )
        label.save()

        response = self.client.get(reverse('label_main', args=[label.pk]))
        self.assertStatusOK(response)

        self.assertContains(response, "Name: Label A")

        self.assertContains(response, "Functional Group: Group 1")

        self.assertContains(response, "Default Short Code: A")

        self.assertInHTML(
            "This is a<br>multiline description.",
            response.content.decode())

        self.assertInHTML(
            '<img src="{}" alt="Label A" class="label-thumbnail">'.format(
                label.thumbnail.url),
            response.content.decode())

        # Too lazy to check the date itself, but there should be a line for it.
        self.assertContains(response, "Create Date:")

        self.assertContains(
            response, "Created By: {}".format(self.user.username))

    def test_duplicate(self):
        labels = self.create_labels(self.user, ['A', 'B'], "Group1")

        # Non-duplicate
        label_a = labels.get(name='A')
        response = self.client.get(reverse('label_main', args=[label_a.pk]))
        self.assertNotContains(response, "THIS LABEL IS A DUPLICATE OF")

        label_b = labels.get(name='B')
        label_b.verified = True
        label_b.save()
        label_a.duplicate = label_b
        label_a.save()

        # Duplicate
        response = self.client.get(reverse('label_main', args=[label_a.pk]))
        self.assertContains(response, "THIS LABEL IS A DUPLICATE OF")
        self.assertInHTML(
            'THIS LABEL IS A DUPLICATE OF: <a href="{}">B</a>'.format(
                reverse('label_main', args=[label_b.pk])
            ),
            response.content.decode())

    def test_verified(self):
        labels = self.create_labels(self.user, ['A'], "Group1")
        label_a = labels.get(name='A')

        response = self.client.get(reverse('label_main', args=[label_a.pk]))
        self.assertInHTML("Verified: No", response.content.decode())

        label_a.verified = True
        label_a.save()

        response = self.client.get(reverse('label_main', args=[label_a.pk]))

        status_icon_html = status_icon_tag(label_a)
        verified_html = 'Verified: Yes {}'.format(status_icon_html)
        self.assertInHTML(verified_html, response.content.decode())

    def test_usage_info(self):
        labels = self.create_labels(self.user, ['A', 'B'], "Group1")
        label_a = labels.get(name='A')

        user_2 = self.create_user()

        user_private_s = self.create_source(
            self.user, visibility=Source.VisibilityTypes.PRIVATE,
            name="User's private source")
        self.create_labelset(self.user, user_private_s, labels)
        img = self.upload_image(self.user, user_private_s)
        self.add_annotations(self.user, img, {1: 'A'})

        # No annotation, but has A in the labelset
        user2_public_s = self.create_source(
            user_2, visibility=Source.VisibilityTypes.PUBLIC,
            name="User 2's public source")
        self.create_labelset(user_2, user2_public_s, labels)

        # Doesn't have A in the labelset
        user_other_s = self.create_source(
            self.user, name="User's other source")
        self.create_labelset(self.user, user_other_s, labels.filter(name='B'))
        img = self.upload_image(self.user, user_other_s)
        self.add_annotations(self.user, img, {1: 'B'})

        self.client.force_login(self.user)
        response = self.client.get(reverse('label_main', args=[label_a.pk]))

        # Usage stats.
        self.assertInHTML(
            'Stats: Used in 2 sources and for 1 annotations',
            response.content.decode())

        # Sources using the label.
        # Viewer's private sources first, with strong links.
        # Then other public sources, with links.
        # (Then other private sources, without links... but these need to have
        # at least 100 images to be listed, so we won't bother testing that
        # here unless we make that threshold flexible.)
        self.assertInHTML(
            '<a href="{}"><strong>{}</strong></a> |'
            ' <a href="{}">{}</a> |'.format(
                reverse('source_main', args=[user_private_s.pk]),
                html_escape("User's private source"),
                reverse('source_main', args=[user2_public_s.pk]),
                html_escape("User 2's public source")),
            response.content.decode())

        # Popularity.
        popularity_str = str(int(label_a.popularity)) + '%'
        popularity_bar_html = popularity_bar_tag(label_a)
        self.assertInHTML(
            'Popularity: {} {}'.format(
                popularity_str, popularity_bar_html),
            response.content.decode())


class LabelMainPatchesTest(ClientTest):
    """
    Test the example annotation patches used by the label detail page.
    """
    @classmethod
    def setUpTestData(cls):
        # Call the parent's setup (while still using this class as cls)
        super().setUpTestData()

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


class LabelMainPatchLinksTest(ClientTest):
    """
    Test the links on the annotation patches.
    """
    @classmethod
    def setUpTestData(cls):
        # Call the parent's setup (while still using this class as cls)
        super().setUpTestData()

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


class PopularityTest(ClientTest):
    """Tests related to label popularity values."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.user = cls.create_user()
        cls.source = cls.create_source(
            cls.user,
            point_generation_type=PointGen.Types.SIMPLE,
            simple_number_of_points=2)

        cls.labels = cls.create_labels(
            cls.user, ['A', 'B'], "Group1")
        cls.label_a = cls.labels.get(name='A')

        cls.img = cls.upload_image(cls.user, cls.source)

    def test_zero_sources(self):
        # There's a labelset, but it doesn't have A
        self.create_labelset(
            self.user, self.source, self.labels.filter(name='B'))

        self.assertEqual(
            self.label_a.popularity, 0,
            msg="0 sources should mean 0 popularity")

    def test_zero_annotations(self):
        # A is in a labelset
        self.create_labelset(self.user, self.source, self.labels)
        # There are annotations, but they're not of A
        self.add_annotations(self.user, self.img, {1: 'B'})

        self.assertEqual(
            self.label_a.popularity, 0,
            msg="1 source and 0 annotations still should mean 0 popularity")

    def test_nonzero_annotations(self):
        # A is in a labelset
        self.create_labelset(self.user, self.source, self.labels)
        # A has annotations (by a quirk of the formula, it actually needs more
        # than 1 annotation to get non-0 popularity)
        self.add_annotations(self.user, self.img, {1: 'A', 2: 'A'})

        self.assertGreater(
            self.label_a.popularity, 0,
            msg="Non-0 annotations should mean non-0 popularity")

    def test_popularity_cached(self):
        # A is in a labelset
        self.create_labelset(self.user, self.source, self.labels)

        self.assertEqual(
            self.label_a.popularity, 0,
            msg="Popularity should be 0")

        # Now A has annotations, and would have non-0 popularity if the
        # cache refreshed
        self.add_annotations(self.user, self.img, {1: 'A', 2: 'A'})

        self.assertEqual(
            self.label_a.popularity, 0,
            msg="Cached popularity of 0 should still be used")


class CalcificationRatesTest(ClientTest):
    """Label-main-page tests related to label calcification rates."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.user = cls.create_user()
        cls.source = cls.create_source(cls.user)

        cls.labels = cls.create_labels(
            cls.user, ['A', 'B'], "Group1")
        cls.label_a = cls.labels.get(name='A')
        cls.label_b = cls.labels.get(name='B')

    def get_label_main(self):
        self.client.force_login(self.user)

        # We'll test on label A's page.
        return self.client.get(reverse('label_main', args=[self.label_a.pk]))

    def test_no_data(self):
        """No calcification rate data for the label."""

        # 2 regions defined, but only label B gets rates
        create_default_calcify_table(
            'Atlantic', {
                self.label_b.pk: dict(mean=2, lower_bound=1, upper_bound=3)})
        create_default_calcify_table(
            'Indo-Pacific', {
                self.label_b.pk: dict(mean=2, lower_bound=1, upper_bound=3)})

        response = self.get_label_main()
        response_soup = BeautifulSoup(response.content, 'html.parser')
        calcify_data_soup = response_soup.find(
            'dd', class_='calcification-rate-data')

        self.assertEqual(
            "(Not available)",
            calcify_data_soup.get_text().strip(),
            msg="Should say rate data isn't available")

    def test_data_for_some_regions(self):
        """
        The label has calcification rate data for at least one, but not
        all of the regions.
        """
        create_default_calcify_table(
            'Atlantic', {
                self.label_b.pk: dict(mean=2, lower_bound=1, upper_bound=3)})
        create_default_calcify_table(
            'Indo-Pacific', {
                self.label_a.pk: dict(mean=5, lower_bound=4, upper_bound=6),
                self.label_b.pk: dict(mean=2, lower_bound=1, upper_bound=3)})

        response = self.get_label_main()
        response_soup = BeautifulSoup(response.content, 'html.parser')
        calcify_data_soup = response_soup.find(
            'dd', class_='calcification-rate-data')

        self.assertNotIn(
            'Atlantic', str(calcify_data_soup),
            msg="Should not have rate data for the Atlantic region")
        self.assertInHTML(
            '<td>Indo-Pacific</td> <td>5</td> <td>4</td> <td>6</td>',
            str(calcify_data_soup),
            msg_prefix="Should include Indo-Pacific rate: ")

    def test_data_for_all_regions(self):
        """
        The label has calcification rate data for all regions.
        """
        create_default_calcify_table(
            'Atlantic', {
                self.label_a.pk: dict(mean=4, lower_bound=3, upper_bound=5),
                self.label_b.pk: dict(mean=2, lower_bound=1, upper_bound=3)})
        create_default_calcify_table(
            'Indo-Pacific', {
                self.label_a.pk: dict(mean=5, lower_bound=4, upper_bound=6),
                self.label_b.pk: dict(mean=2, lower_bound=1, upper_bound=3)})

        response = self.get_label_main()
        response_soup = BeautifulSoup(response.content, 'html.parser')
        calcify_data_soup = response_soup.find(
            'dd', class_='calcification-rate-data')

        self.assertInHTML(
            '<td>Atlantic</td> <td>4</td> <td>3</td> <td>5</td>',
            str(calcify_data_soup),
            msg_prefix="Should include Atlantic rate: ")
        self.assertInHTML(
            '<td>Indo-Pacific</td> <td>5</td> <td>4</td> <td>6</td>',
            str(calcify_data_soup),
            msg_prefix="Should include Indo-Pacific rate: ")

    def test_links_to_default_tables(self):
        """
        The calcification rates help dialog should have download links to the
        latest default tables.
        """
        atlantic_table = create_default_calcify_table(
            'Atlantic', {
                self.label_b.pk: dict(mean=2, lower_bound=1, upper_bound=3)})
        indo_pacific_table = create_default_calcify_table(
            'Indo-Pacific', {
                self.label_a.pk: dict(mean=5, lower_bound=4, upper_bound=6),
                self.label_b.pk: dict(mean=2, lower_bound=1, upper_bound=3)})

        response = self.get_label_main()
        response_soup = BeautifulSoup(response.content, 'html.parser')
        help_dialog_tag = response_soup.select('div.tutorial-message')[0]

        atlantic_download_url = reverse(
            'calcification:rate_table_download', args=[atlantic_table.pk])
        indo_pacific_download_url = reverse(
            'calcification:rate_table_download', args=[indo_pacific_table.pk])
        self.assertInHTML(
            f'<a href="{atlantic_download_url}">Atlantic</a>',
            str(help_dialog_tag),
            msg_prefix="Atlantic table download link should be present")
        self.assertInHTML(
            f'<a href="{indo_pacific_download_url}">Indo-Pacific</a>',
            str(help_dialog_tag),
            msg_prefix="Indo-Pacific table download link should be present")
