import numpy as np

from django.conf import settings
from django.core.urlresolvers import reverse

from lib.test_utils import ClientTest

from labels.models import Label
from images.models import Source, Image, Point
from annotations.models import Annotation
from accounts.utils import get_robot_user
from .models import Score, Classifier
from .tasks import reset_after_labelset_change

import vision_backend.task_helpers as th


class ResetTaskTest(ClientTest):

    @classmethod
    def setUpTestData(cls):
        super(ResetTaskTest, cls).setUpTestData()

        cls.user = cls.create_user()
        cls.source = cls.create_source(cls.user)

        labels = cls.create_labels(cls.user, ['A', 'B', 'C', 'D', 'E', 'F', 'G'], "Group1")

        cls.create_labelset(cls.user, cls.source, labels.filter(
            name__in=['A', 'B', 'C', 'D', 'E', 'F', 'G'])
        )


    def test_labelset_change_cleanup(self):
        """
        If the labelset is changed, the whole backend must be reset.
        """

        # Create some dummy classifiers
        Classifier(source = self.source).save()
        Classifier(source = self.source).save()

        self.assertEqual(Classifier.objects.filter(source = self.source).count(), 2)

        # Create some dummy scores
        img = self.upload_image(self.user, self.source)

        # Pre-fetch label objects
        label_objs = self.source.labelset.get_globals()

        # Check number of points per image
        nbr_points = Point.objects.filter(image = img).count()

        # Fake creation of scores.
        scores = []
        for i in range(nbr_points):
            scores.append(np.random.rand(label_objs.count()))
        th._add_scores(img.pk, scores, label_objs)

        expected_nbr_scores = min(5, label_objs.count())
        self.assertEqual(Score.objects.filter(image = img).count(), nbr_points * expected_nbr_scores)

        # Fake that the image is classified
        img.features.classified = True
        img.features.save()
        self.assertTrue(Image.objects.get(id = img.id).features.classified)

        #Now, reset the source.
        reset_after_labelset_change(self.source.id)

        self.assertEqual(Classifier.objects.filter(source = self.source).count(), 0)
        self.assertEqual(Score.objects.filter(image = img).count(), 0)
        self.assertFalse(Image.objects.get(id = img.id).features.classified)

    def test_point_change_clenup(self):
        """
        If we genereate new point, features must be reset.
        """
        img = self.upload_image(self.user, self.source)
        img.features.extracted = True
        img.features.classified = True
        img.features.save()

        self.assertTrue(Image.objects.get(id = img.id).features.extracted)
        self.assertTrue(Image.objects.get(id = img.id).features.classified)

        self.client.force_login(self.user)
        url = reverse('image_detail', kwargs=dict(image_id = img.id))
        data = dict(
            regenerate_point_locations="Any arbitrary string goes here"
        )
        self.client.post(url, data)

        # Now features should be reset
        self.assertFalse(Image.objects.get(id = img.id).features.extracted)
        self.assertFalse(Image.objects.get(id = img.id).features.classified)


class ClassifyImageTask(ClientTest):

    @classmethod
    def setUpTestData(cls):
        super(ClassifyImageTask, cls).setUpTestData()

        cls.user = cls.create_user()
        cls.source = cls.create_source(cls.user)

        labels = cls.create_labels(cls.user, ['A', 'B', 'C', 'D', 'E', 'F', 'G'], "Group1")

        cls.create_labelset(cls.user, cls.source, labels.filter(
            name__in=['A', 'B', 'C', 'D', 'E', 'F', 'G'])
        )

        cls.dummy_annotations = dict(
            label_1='A', label_2='B', label_3='C',label_4='D', label_5='E', label_6='F',
            robot_1='false', robot_2='false', robot_3='false', robot_4='false', robot_5='false', robot_6='false',
        )

        cls.partial_dummy_annotations = dict(
            label_1='A',
            robot_1='false',
        )
    
    @classmethod
    def annotate(self, img_id, user, data):
        self.client.force_login(user)
        url = reverse('save_annotations_ajax', kwargs=dict(image_id = img_id))
        return self.client.post(url, data).json()


    def test_classify_image(self):
        """
        Test basic dynamics of image upload.
        """
        # Upload three images
        img1 = self.upload_image(self.user, self.source)
        img2 = self.upload_image(self.user, self.source)
        img3 = self.upload_image(self.user, self.source)
        
        # Annotate the second one partially and the third fully
        self.annotate(img2.id, self.user, self.partial_dummy_annotations)
        self.annotate(img3.id, self.user, self.dummy_annotations)

        # Remember which were annotated for img2
        human_anns = list(Annotation.objects.filter(image_id = img2.id))

        
        # Pretent that all images were classified
        for img in [img1, img2, img3]:
            img.features.extracted = True
            img.features.classified = True
            img.features.save()

        clf = Classifier(source = self.source)
        clf.valid = True
        clf.save()

        # Pre-fetch label objects
        label_objs = self.source.labelset.get_globals()

        # Check number of points per image
        nbr_points = Point.objects.filter(image = img1).count()

        # Fake creation of scores.
        scores = []
        for i in range(nbr_points):
            scores.append(np.random.rand(label_objs.count()))

        for img in [img1, img2, img3]:    
            th._add_scores(img.pk, scores, label_objs)
            th._add_annotations(img.pk, scores, label_objs, clf)

        # Check the annotations. 
        r = self.source.get_latest_robot()

        # Img1 whould have only robot annotations
        for ann in Annotation.objects.filter(image_id = img1.id):
            self.assertTrue(ann.user == get_robot_user())

        # Img2 should have a mix.
        for ann in Annotation.objects.filter(image_id = img2.id):
            if ann in human_anns:
                self.assertFalse(ann.user == get_robot_user())
            else:
                self.assertTrue(ann.user == get_robot_user())

        # Img3 should have only manual annotations.    
        for ann in Annotation.objects.filter(image_id = img3.id):
            self.assertFalse(ann.user == get_robot_user())

        # Check that max score label corresponds to the annotation for each point for img1.
        for point in Point.objects.filter(image = img1):
            ann = Annotation.objects.get(point = point)
            scores = Score.objects.filter(point = point)
            posteriors = [score.score for score in scores]
            self.assertEqual(scores[np.argmax(posteriors)].label, ann.label)
