from __future__ import unicode_literals

from django.contrib.auth.models import Group
from django.core.cache import cache
from django.urls import reverse

from images.model_utils import PointGen
from lib.tests.utils import BasePermissionTest, ClientTest
from ..models import LabelGroup, Label


class PermissionTest(BasePermissionTest):

    @classmethod
    def setUpTestData(cls):
        super(PermissionTest, cls).setUpTestData()

        cls.labels = cls.create_labels(cls.user, ['A', 'B'], 'GroupA')

    def test_label_list(self):
        url = reverse('label_list')
        template = 'labels/label_list.html'

        self.assertPermissionLevel(url, self.SIGNED_OUT, template=template)

    def test_label_list_search_ajax(self):
        url = reverse('label_list_search_ajax')

        self.assertPermissionLevel(url, self.SIGNED_OUT, is_json=True)


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


class BaseLabelSearchTest(ClientTest):

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
        data.update(kwargs)
        response = self.client.get(self.url, data)
        return response

    def setUp(self):
        super(BaseLabelSearchTest, self).setUp()

        # Popularities are cached when computed, so we clear the cache to
        # prevent a previous test from affecting the next one.
        cache.clear()


class LabelSearchNameFieldTest(BaseLabelSearchTest):
    """
    Test the name field of the Ajax label search.
    """
    @classmethod
    def setUpTestData(cls):
        super(LabelSearchNameFieldTest, cls).setUpTestData()

        cls.user = cls.create_user()
        cls.url = reverse('label_list_search_ajax')

    def test_match_full_name(self):
        self.create_labels(self.user, ["Red", "Blue"], "Group1")

        response = self.submit_search(name_search="Red")
        self.assertLabels(response, ["Red"])

    def test_match_part_of_name(self):
        self.create_labels(self.user, ["Red", "Blue"], "Group1")

        response = self.submit_search(name_search="Blu")
        self.assertLabels(response, ["Blue"])

    def test_match_case_insensitive(self):
        self.create_labels(self.user, ["Red", "Blue"], "Group1")

        response = self.submit_search(name_search="BLUE")
        self.assertLabels(response, ["Blue"])

    def test_match_multiple_labels(self):
        self.create_labels(
            self.user, ["Red", "Light Blue", "Dark Blue"], "Group1")

        response = self.submit_search(name_search="Blue")
        self.assertLabels(response, ["Light Blue", "Dark Blue"])

    def test_multiple_words(self):
        self.create_labels(
            self.user, ["Light Blue", "Dark Blue", "Dark Red"], "Group1")

        response = self.submit_search(name_search="Dark Blue")
        self.assertLabels(response, ["Dark Blue"])

    def test_no_match(self):
        self.create_labels(self.user, ["Red", "Blue"], "Group1")

        response = self.submit_search(name_search="Green")
        self.assertLabels(response, [])

    def test_strip_whitespace(self):
        self.create_labels(self.user, ["Blue", "Red"], "Group1")

        response = self.submit_search(name_search="  Blue ")
        self.assertLabels(response, ["Blue"])

    def test_normalize_multiple_spaces(self):
        self.create_labels(
            self.user, ["Light Blue", "Dark Blue", "Dark Red"], "Group1")

        response = self.submit_search(name_search="Dark   Blue")
        self.assertLabels(response, ["Dark Blue"])

    def test_treat_punctuation_as_spaces(self):
        self.create_labels(
            self.user, ["Light Blue", "Dark Blue", "Dark Red"], "Group1")

        response = self.submit_search(name_search=";'Dark_/Blue=-")
        self.assertLabels(response, ["Dark Blue"])

    def test_no_tokens(self):
        self.create_labels(
            self.user, ["Light Blue", "Dark Blue", "Dark Red"], "Group1")

        response = self.submit_search(name_search=";'_/=-")
        self.assertLabels(response, [])


class LabelSearchOtherFieldsTest(BaseLabelSearchTest):
    """Test fields other than name."""
    @classmethod
    def setUpTestData(cls):
        super(LabelSearchOtherFieldsTest, cls).setUpTestData()

        cls.user = cls.create_user()
        cls.url = reverse('label_list_search_ajax')

        cls.create_labels(cls.user, ['A', 'B'], "Group1")
        cls.create_labels(cls.user, ['C', 'D'], "Group2")

    def test_show_by_status(self):
        label_a = Label.objects.get(name='A')
        label_a.verified = True
        label_a.save()
        label_b = Label.objects.get(name='B')
        label_b.duplicate = label_a
        label_b.save()

        response = self.submit_search(
            show_verified=False, show_regular=False, show_duplicate=False)
        self.assertLabels(response, [])

        response = self.submit_search(
            show_verified=True, show_regular=False, show_duplicate=False)
        self.assertLabels(response, ['A'])

        response = self.submit_search(
            show_verified=False, show_regular=True, show_duplicate=False)
        self.assertLabels(response, ['C', 'D'])

        response = self.submit_search(
            show_verified=False, show_regular=False, show_duplicate=True)
        self.assertLabels(response, ['B'])

        response = self.submit_search(
            show_verified=True, show_regular=True, show_duplicate=False)
        self.assertLabels(response, ['A', 'C', 'D'])

        response = self.submit_search(
            show_verified=True, show_regular=True, show_duplicate=True)
        self.assertLabels(response, ['A', 'B', 'C', 'D'])

    def test_show_by_functional_group(self):
        response = self.submit_search()
        self.assertLabels(response, ['A', 'B', 'C', 'D'])

        response = self.submit_search(
            functional_group=LabelGroup.objects.get(name='Group1').pk)
        self.assertLabels(response, ['A', 'B'])

        response = self.submit_search(
            functional_group=LabelGroup.objects.get(name='Group2').pk)
        self.assertLabels(response, ['C', 'D'])

    def test_show_by_popularity(self):
        source = self.create_source(
            self.user,
            point_generation_type=PointGen.Types.SIMPLE,
            simple_number_of_points=4)
        self.create_labelset(self.user, source, Label.objects.all())
        img = self.upload_image(self.user, source)
        self.add_annotations(
            self.user, img, {1: 'A', 2: 'A', 3: 'C', 4: 'C'})

        response = self.submit_search()
        self.assertLabels(response, ['A', 'B', 'C', 'D'])

        response = self.submit_search(min_popularity=1)
        self.assertLabels(response, ['A', 'C'])

    def test_multiple_filters(self):
        label_a = Label.objects.get(name='A')
        label_b = Label.objects.get(name='B')
        label_c = Label.objects.get(name='C')

        # A, B, and C are verified
        label_a.verified = True
        label_a.save()
        label_b.verified = True
        label_b.save()
        label_c.verified = True
        label_c.save()

        # A and B are already in Group1

        # A and C have popularity
        source = self.create_source(
            self.user,
            point_generation_type=PointGen.Types.SIMPLE,
            simple_number_of_points=4)
        self.create_labelset(self.user, source, Label.objects.all())
        img = self.upload_image(self.user, source)
        self.add_annotations(
            self.user, img, {1: 'A', 2: 'A', 3: 'C', 4: 'C'})

        # Only A satisfies all requirements here
        response = self.submit_search(
            show_verified=True, show_regular=False,
            functional_group=LabelGroup.objects.get(name='Group1').pk,
            min_popularity=1)
        self.assertLabels(response, ['A'])
