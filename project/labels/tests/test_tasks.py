from jobs.models import Job
from jobs.utils import queue_job
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

    @staticmethod
    def run_and_get_result():
        # Note that this may or may not queue a new job instance; perhaps
        # the periodic job was already queued at the end of the previous
        # job's run.
        queue_job('update_label_popularities')
        update_label_popularities()
        job = Job.objects.filter(
            job_name='update_label_popularities',
            status=Job.Status.SUCCESS).latest('pk')
        return job.result_message

    def test_set_on_demand(self):
        self.assertAlmostEqual(self.label_a.popularity, 5, places=0)

    def test_set_in_advance(self):
        self.assertEqual(
            self.run_and_get_result(),
            "Updated popularities for all 2 label(s)")
        self.assertAlmostEqual(self.label_a.popularity, 5, places=0)

    def test_set_then_update(self):
        self.run_and_get_result()
        self.assertAlmostEqual(self.label_a.popularity, 5, places=0)
        self.add_annotations(self.user, self.img, {4: 'A'})
        self.run_and_get_result()
        self.assertAlmostEqual(self.label_a.popularity, 8, places=0)

    def test_caching(self):
        self.run_and_get_result()
        self.assertAlmostEqual(self.label_a.popularity, 5, places=0)
        self.add_annotations(self.user, self.img, {4: 'A'})
        self.assertAlmostEqual(self.label_a.popularity, 5, places=0)
