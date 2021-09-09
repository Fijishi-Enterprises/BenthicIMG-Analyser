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
        super().setUpTestData()

    def test_features_extracted_false(self):
        self.user = self.create_user()
        self.source = self.create_source(self.user)
        self.img1 = self.upload_image(self.user, self.source)
        self.assertFalse(self.img1.features.extracted)


class CascadeDeleteTest(ClientTest):

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()

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


class PopulateClassifierStatusTest(MigrationTest):

    app_name = 'vision_backend'
    before = '0002_classifier_status'
    after = '0003_populate_classifier_status'

    def test_migration(self):
        Source = self.get_model_before('images.Source')
        Classifier = self.get_model_before('vision_backend.Classifier')

        source = Source(name="Test source")
        source.save()
        classifier_accepted = Classifier(
            source=source, valid=True, accuracy=0.50)
        classifier_accepted.save()
        classifier_rejected = Classifier(
            source=source, valid=False, accuracy=0.50)
        classifier_rejected.save()
        classifier_error = Classifier(
            source=source, valid=False)
        classifier_error.save()

        self.run_migration()

        # Statuses should be populated based on the other fields
        classifier_accepted.refresh_from_db()
        self.assertEqual(
            classifier_accepted.status, 'AC')
        classifier_rejected.refresh_from_db()
        self.assertEqual(
            classifier_rejected.status, 'RJ')
        classifier_error.refresh_from_db()
        self.assertEqual(
            classifier_error.status, 'ER')
