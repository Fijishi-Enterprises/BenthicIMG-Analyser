from lib.tests.utils import ClientTest
from ..tasks import update_label_popularities


class UpdatePopularityTest(ClientTest):
    """
    Test updates of label popularities.
    """
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.user = cls.create_user()
        cls.source = cls.create_source(cls.user)
        labels = cls.create_labels(cls.user, ['A', 'B'], "Group1")
        cls.label_a = labels.get(name='A')

        cls.create_labelset(cls.user, cls.source, labels)
        cls.img = cls.upload_image(cls.user, cls.source)
        cls.add_annotations(cls.user, cls.img, {1: 'A', 2: 'B', 3: 'A'})

    def test_set_on_demand(self):
        self.assertAlmostEqual(self.label_a.popularity, 5, places=0)

    def test_set_in_advance(self):
        update_label_popularities.delay()
        self.assertAlmostEqual(self.label_a.popularity, 5, places=0)

    def test_set_then_update(self):
        update_label_popularities.delay()
        self.assertAlmostEqual(self.label_a.popularity, 5, places=0)
        self.add_annotations(self.user, self.img, {4: 'A'})
        update_label_popularities.delay()
        self.assertAlmostEqual(self.label_a.popularity, 8, places=0)

    def test_caching(self):
        update_label_popularities.delay()
        self.assertAlmostEqual(self.label_a.popularity, 5, places=0)
        self.add_annotations(self.user, self.img, {4: 'A'})
        self.assertAlmostEqual(self.label_a.popularity, 5, places=0)
