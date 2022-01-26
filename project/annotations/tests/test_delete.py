from unittest import skip

from django.urls import reverse
import spacer.config as spacer_config

from lib.tests.utils import BasePermissionTest, ClientTest
from vision_backend.tasks import collect_all_jobs, submit_classifier


class PermissionTest(BasePermissionTest):
    """
    Test view permissions.
    """
    def test_batch_delete_annotations_ajax(self):
        url = reverse('batch_delete_annotations_ajax', args=[self.source.pk])

        self.source_to_private()
        self.assertPermissionLevel(
            url, self.SOURCE_EDIT, is_json=True, post_data={})
        self.source_to_public()
        self.assertPermissionLevel(
            url, self.SOURCE_EDIT, is_json=True, post_data={})


class BaseDeleteTest(ClientTest):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()

        cls.user = cls.create_user()
        cls.source = cls.create_source(cls.user, simple_number_of_points=2)
        cls.labels = cls.create_labels(cls.user, ['A', 'B'], "Group1")
        cls.create_labelset(cls.user, cls.source, cls.labels)

        cls.url = reverse(
            'batch_delete_annotations_ajax', args=[cls.source.pk])

        cls.default_search_params = dict(
            image_form_type='search',
            aux1='', aux2='', aux3='', aux4='', aux5='',
            height_in_cm='', latitude='', longitude='', depth='',
            photographer='', framing='', balance='',
            photo_date_0='', photo_date_1='', photo_date_2='',
            photo_date_3='', photo_date_4='',
            image_name='', annotation_status='',
            last_annotated_0='', last_annotated_1='', last_annotated_2='',
            last_annotated_3='', last_annotated_4='',
            last_annotator_0='', last_annotator_1='',
            sort_method='name', sort_direction='asc',
        )

    def assert_annotations_deleted(self, image):
        self.assertFalse(
            image.annotation_set.exists(),
            f"Image {image.metadata.name}'s annotations should be deleted")
        self.assertFalse(
            image.annoinfo.confirmed,
            f"Image {image.metadata.name} should not be confirmed anymore")

    def assert_annotations_not_deleted(self, image):
        self.assertEqual(
            image.annotation_set.count(), 2,
            f"Image {image.metadata.name} should still have its annotations")
        self.assertTrue(
            image.annoinfo.confirmed,
            f"Image {image.metadata.name} should still be confirmed")

    def assert_confirmation_message(self, count):
        """
        Call this after a successful deletion to check the top-of-page
        confirmation message.
        """
        browse_url = reverse('browse_images', args=[self.source.pk])
        self.client.force_login(self.user)
        response = self.client.get(browse_url)
        self.assertContains(
            response,
            f"The {count} selected images have had their annotations deleted.")


class SuccessTest(BaseDeleteTest):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()

        cls.img1 = cls.upload_image(
            cls.user, cls.source, dict(filename='1.png'))
        cls.img2 = cls.upload_image(
            cls.user, cls.source, dict(filename='2.png'))
        cls.img3 = cls.upload_image(
            cls.user, cls.source, dict(filename='3.png'))

    def setUp(self):
        super().setUp()

        for image in [self.img1, self.img2, self.img3]:
            image.refresh_from_db()
            self.add_annotations(self.user, image, {1: 'A', 2: 'B'})

    def test_delete_for_all_images(self):
        """
        Delete annotations for all images in the source.
        """
        self.client.force_login(self.user)
        response = self.client.post(self.url, self.default_search_params)
        self.assertDictEqual(response.json(), dict(success=True))

        for image in [self.img1, self.img2, self.img3]:
            self.assert_annotations_deleted(image)

        self.assert_confirmation_message(count=3)

    def test_delete_by_aux_meta(self):
        """
        Delete when filtering images by auxiliary metadata.
        """
        self.img1.metadata.aux1 = 'SiteA'
        self.img1.metadata.save()

        post_data = self.default_search_params.copy()
        post_data['aux1'] = 'SiteA'

        self.client.force_login(self.user)
        response = self.client.post(self.url, post_data)
        self.assertDictEqual(response.json(), dict(success=True))

        self.assert_annotations_deleted(self.img1)
        self.assert_annotations_not_deleted(self.img2)
        self.assert_annotations_not_deleted(self.img3)

        self.assert_confirmation_message(count=1)

    def test_delete_by_image_ids(self):
        """
        Delete when filtering images by image ids.
        """
        post_data = dict(
            image_form_type='ids',
            ids=','.join([str(self.img1.pk), str(self.img3.pk)])
        )

        self.client.force_login(self.user)
        response = self.client.post(self.url, post_data)
        self.assertDictEqual(response.json(), dict(success=True))

        self.assert_annotations_deleted(self.img1)
        self.assert_annotations_not_deleted(self.img2)
        self.assert_annotations_deleted(self.img3)

        self.assert_confirmation_message(count=2)


class NotFullyAnnotatedTest(BaseDeleteTest):
    """
    Should work fine when some images aren't fully annotated.
    """
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()

        cls.img1 = cls.upload_image(
            cls.user, cls.source, dict(filename='1.png'))
        cls.add_annotations(cls.user, cls.img1, {1: 'A', 2: 'B'})
        # One annotation, two points
        cls.img2 = cls.upload_image(
            cls.user, cls.source, dict(filename='2.png'))
        cls.add_annotations(cls.user, cls.img2, {1: 'A'})
        # No annotations
        cls.img3 = cls.upload_image(
            cls.user, cls.source, dict(filename='3.png'))

    def test(self):
        self.client.force_login(self.user)
        response = self.client.post(self.url, self.default_search_params)
        self.assertDictEqual(response.json(), dict(success=True))

        for image in [self.img1, self.img2, self.img3]:
            self.assert_annotations_deleted(image)


@skip("This test fails intermittently (at least in CI) for some reason.")
class ClassifyAfterDeleteTest(BaseDeleteTest):
    """
    Should machine-classify the images after annotation deletion,
    assuming there's a classifier available.
    """
    def upload_image_with_annotations(self, filename):
        img = self.upload_image(
            self.user, self.source, image_options=dict(filename=filename))
        self.add_annotations(self.user, img, {1: 'A', 2: 'B'})
        return img

    def upload_images_for_training(self, train_image_count, val_image_count):
        for _ in range(train_image_count):
            self.upload_image_with_annotations(
                'train{}.png'.format(self.image_count))
        for _ in range(val_image_count):
            self.upload_image_with_annotations(
                'val{}.png'.format(self.image_count))

    def upload_data_and_train_classifier(self):
        # Provide enough data for training
        self.upload_images_for_training(
            train_image_count=spacer_config.MIN_TRAINIMAGES, val_image_count=1)
        # Process feature extraction results
        collect_all_jobs()

        # Train classifier
        submit_classifier(self.source.pk)
        collect_all_jobs()

    def test(self):
        # Set up confirmed images + classifier
        self.upload_data_and_train_classifier()

        # Set up one unconfirmed image; we want to check that the unconfirmed
        # annotations can get re-added after being deleted.
        unconfirmed_image = self.upload_image(
            self.user, self.source,
            image_options=dict(filename='unconfirmed.png'))
        collect_all_jobs()
        unconfirmed_image.refresh_from_db()
        self.assertEqual(
            unconfirmed_image.annotation_set.unconfirmed().count(), 2,
            f"Image {unconfirmed_image.metadata.name} should have"
            f" unconfirmed annotations")

        # Delete annotations
        self.client.force_login(self.user)
        response = self.client.post(self.url, self.default_search_params)
        self.assertDictEqual(response.json(), dict(success=True))

        for image in self.source.image_set.all():
            self.assertFalse(
                image.annotation_set.confirmed().exists(),
                f"Image {image.metadata.name}'s confirmed annotations"
                f" should be deleted")
            self.assertEqual(
                image.annotation_set.unconfirmed().count(), 2,
                f"Image {image.metadata.name} should now have"
                f" unconfirmed annotations")
            self.assertFalse(
                image.annoinfo.confirmed,
                f"Image {image.metadata.name} should not be confirmed anymore")


class OtherSourceTest(BaseDeleteTest):
    """
    Ensure that the view doesn't allow deleting other sources' annotations.
    """
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()

        cls.img1 = cls.upload_image(
            cls.user, cls.source, dict(filename='1.png'))
        cls.img2 = cls.upload_image(
            cls.user, cls.source, dict(filename='2.png'))

        source2 = cls.create_source(cls.user, simple_number_of_points=2)
        cls.create_labelset(cls.user, source2, cls.labels)
        cls.img21 = cls.upload_image(
            cls.user, source2, dict(filename='21.png'))
        cls.img22 = cls.upload_image(
            cls.user, source2, dict(filename='22.png'))

    def setUp(self):
        super().setUp()

        for image in [self.img1, self.img2, self.img21, self.img22]:
            image.refresh_from_db()
            self.add_annotations(self.user, image, {1: 'A', 2: 'B'})

    def test_dont_delete_from_other_sources_via_search_form(self):
        """
        Sanity check that the search form only picks up images in the current
        source.
        """
        self.client.force_login(self.user)
        response = self.client.post(self.url, self.default_search_params)
        self.assertDictEqual(response.json(), dict(success=True))

        self.assert_annotations_deleted(self.img1)
        self.assert_annotations_deleted(self.img2)

        self.assert_annotations_not_deleted(self.img21)
        self.assert_annotations_not_deleted(self.img22)

    def test_dont_delete_from_other_sources_via_ids(self):
        """
        Sanity check that specifying by IDs only accepts images in the current
        source.
        """
        post_data = dict(
            image_form_type='ids',
            ids=','.join([str(self.img1.pk), str(self.img22.pk)])
        )

        self.client.force_login(self.user)
        response = self.client.post(self.url, post_data)
        self.assertDictEqual(response.json(), dict(success=True))

        self.assert_annotations_deleted(self.img1)
        self.assert_annotations_not_deleted(self.img22)


class ErrorTest(BaseDeleteTest):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()

        cls.img1 = cls.upload_image(
            cls.user, cls.source, dict(filename='1.png'))
        cls.img2 = cls.upload_image(
            cls.user, cls.source, dict(filename='2.png'))
        cls.img3 = cls.upload_image(
            cls.user, cls.source, dict(filename='3.png'))

    def setUp(self):
        super().setUp()

        for image in [self.img1, self.img2, self.img3]:
            image.refresh_from_db()
            self.add_annotations(self.user, image, {1: 'A', 2: 'B'})

    def test_no_search_form(self):
        self.client.force_login(self.user)
        response = self.client.post(self.url, dict())
        self.assertDictEqual(response.json(), dict(
            error=(
                "You must first use the search form or select images on the"
                " page to use the delete function. If you really want to"
                " delete all images' annotations, first click 'Search' without"
                " changing any of the search fields."
            )
        ))

        for image in [self.img1, self.img2, self.img3]:
            self.assert_annotations_not_deleted(image)

    def test_form_error(self):
        post_data = self.default_search_params.copy()
        post_data['annotation_status'] = 'invalid_value'

        self.client.force_login(self.user)
        response = self.client.post(self.url, post_data)
        self.assertDictEqual(response.json(), dict(
            error=(
                "There was an error with the form."
                " Nothing was deleted."
            )
        ))

        for image in [self.img1, self.img2, self.img3]:
            self.assert_annotations_not_deleted(image)
