import mock

from django_migration_testcase import MigrationTest
import numpy as np
from spacer.messages import ClassifyReturnMsg

from lib.tests.utils import ClientTest
from images.models import Point
from vision_backend.models import Score
import vision_backend.task_helpers as th


class ImageInitialStatusTest(ClientTest):
    """
    Check a newly uploaded image's status (as relevant to the vision backend).
    """
    @classmethod
    def setUpTestData(cls):
        super(ImageInitialStatusTest, cls).setUpTestData()

    def test_features_extracted_false(self):
        self.user = self.create_user()
        self.source = self.create_source(self.user)
        self.img1 = self.upload_image(self.user, self.source)
        self.assertFalse(self.img1.features.extracted)


class CascadeDeleteTest(ClientTest):

    @classmethod
    def setUpTestData(cls):
        super(CascadeDeleteTest, cls).setUpTestData()

        cls.user = cls.create_user()
        cls.source = cls.create_source(cls.user)
    
        labels = cls.create_labels(cls.user,
                                   ['A', 'B', 'C', 'D', 'E', 'F', 'G'],
                                   "Group1")

        cls.create_labelset(cls.user, cls.source, labels.filter(
            name__in=['A', 'B', 'C', 'D', 'E', 'F', 'G'])
        )

    def test_point_score_cascade(self):
        """
        If a point is deleted all scores for that point should be deleted.
        """
        img = self.upload_image(self.user, self.source)

        # Pre-fetch label objects
        label_objs = self.source.labelset.get_globals()

        # Check number of points per image
        nbr_points = Point.objects.filter(image=img).count()

        # Fake creation of scores.
        scores = []
        for i in range(nbr_points):
            scores.append(np.random.rand(label_objs.count()))

        return_msg = ClassifyReturnMsg(
            runtime=0.0,
            scores=[(0, 0, [float(s) for s in scrs]) for scrs in scores],
            classes=[label.pk for label in label_objs],
            valid_rowcol=False,
        )

        th.add_scores(img.pk, return_msg, label_objs)

        expected_nbr_scores = min(5, label_objs.count())
        self.assertEqual(Score.objects.filter(image=img).count(),
                         nbr_points * expected_nbr_scores)
        
        # remove one point
        points = Point.objects.filter(image=img)
        points[0].delete()

        # Now all scores for that point should be gone.
        self.assertEqual(Score.objects.filter(image=img).count(),
                         (nbr_points - 1) * expected_nbr_scores)


class FeaturesImageFieldMigrationTest(MigrationTest):
    """
    Test porting from Image.features field to Features.image field.
    """

    before = [
        ('images', '0028_change_default_extractor'),
        ('vision_backend', '0006_batchjob'),
    ]
    after = [
        ('images', '0031_remove_image_features'),
        ('vision_backend', '0011_features_image_non_null'),
    ]

    image_defaults = dict(
        original_width=100,
        original_height=100,
    )

    def test_images_and_features_remain_paired(self):
        """
        Images and Features that were paired before should remain paired after.
        """
        Source = self.get_model_before('images.Source')
        Metadata = self.get_model_before('images.Metadata')
        Image = self.get_model_before('images.Image')
        Features = self.get_model_before('vision_backend.Features')

        source = Source.objects.create()

        features_1 = Features.objects.create()
        features_1_pk = features_1.pk
        metadata_1 = Metadata.objects.create()
        image_1 = Image.objects.create(
            source=source, metadata=metadata_1,
            features=features_1, **self.image_defaults)
        image_1_pk = image_1.pk

        features_2 = Features.objects.create()
        features_2_pk = features_2.pk
        metadata_2 = Metadata.objects.create()
        image_2 = Image.objects.create(
            source=source, metadata=metadata_2,
            features=features_2, **self.image_defaults)
        image_2_pk = image_2.pk

        # Feature.image attributes shouldn't exist yet
        self.assertRaises(AttributeError, getattr, features_1, 'image')
        self.assertRaises(AttributeError, getattr, features_2, 'image')

        self.run_migration()

        Features = self.get_model_after('vision_backend.Features')

        # Attributes should be filled in
        self.assertEqual(
            Features.objects.get(pk=features_1_pk).image.pk, image_1_pk)
        self.assertEqual(
            Features.objects.get(pk=features_2_pk).image.pk, image_2_pk)

    def test_clean_up_features_without_images(self):
        """
        Features without a corresponding Image should get cleaned up.
        """
        Source = self.get_model_before('images.Source')
        Metadata = self.get_model_before('images.Metadata')
        Image = self.get_model_before('images.Image')
        Features = self.get_model_before('vision_backend.Features')

        source = Source.objects.create()

        features_1 = Features.objects.create()
        features_1_pk = features_1.pk
        metadata_1 = Metadata.objects.create()
        Image.objects.create(
            source=source, metadata=metadata_1,
            features=features_1, **self.image_defaults)

        features_2 = Features.objects.create()
        features_2_pk = features_2.pk

        def input_without_prompt(_):
            """
            Bypass the input prompt by mocking input(). This just returns a
            constant value.
            """
            return 'y'
        def print_noop(_):
            """Don't print output during the migration run."""
            pass
        input_mock_target = \
            'vision_backend.migrations.0010_features_image_null_cleanup.input'
        print_mock_target = \
            'vision_backend.migrations.0010_features_image_null_cleanup.print'
        with mock.patch(input_mock_target, input_without_prompt):
            with mock.patch(print_mock_target, print_noop):
                self.run_migration()

        Features = self.get_model_after('vision_backend.Features')
        # This should still exist (should not raise error)
        Features.objects.get(pk=features_1_pk)
        # This shouldn't exist anymore
        self.assertRaises(
            Features.DoesNotExist, Features.objects.get, pk=features_2_pk)


class FeaturesImageFieldBackwardsMigrationTest(MigrationTest):
    """
    Test porting from Features.image field back to Image.features field.
    """

    before = [
        ('images', '0031_remove_image_features'),
        ('vision_backend', '0011_features_image_non_null'),
    ]
    after = [
        ('images', '0028_change_default_extractor'),
        ('vision_backend', '0006_batchjob'),
    ]

    image_defaults = dict(
        original_width=100,
        original_height=100,
    )

    def test_images_and_features_remain_paired(self):
        """
        Images and Features that were paired before should remain paired after.
        """
        Source = self.get_model_before('images.Source')
        Metadata = self.get_model_before('images.Metadata')
        Image = self.get_model_before('images.Image')
        Features = self.get_model_before('vision_backend.Features')

        source = Source.objects.create()

        metadata_1 = Metadata.objects.create()
        image_1 = Image.objects.create(
            source=source, metadata=metadata_1,
            **self.image_defaults)
        image_1_pk = image_1.pk
        features_1 = Features.objects.create(image=image_1)
        features_1_pk = features_1.pk

        metadata_2 = Metadata.objects.create()
        image_2 = Image.objects.create(
            source=source, metadata=metadata_2,
            **self.image_defaults)
        image_2_pk = image_2.pk
        features_2 = Features.objects.create(image=image_2)
        features_2_pk = features_2.pk

        self.run_migration()

        Image = self.get_model_after('images.Image')
        Features = self.get_model_after('vision_backend.Features')

        # Image.features should be filled in
        self.assertEqual(
            Image.objects.get(pk=image_1_pk).features.pk, features_1_pk)
        self.assertEqual(
            Image.objects.get(pk=image_2_pk).features.pk, features_2_pk)

        # Feature.image attributes shouldn't exist anymore
        self.assertRaises(
            AttributeError, getattr,
            Features.objects.get(pk=features_1_pk), 'image')
        self.assertRaises(
            AttributeError, getattr,
            Features.objects.get(pk=features_2_pk), 'image')
