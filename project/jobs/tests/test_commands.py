from lib.tests.utils import ManagementCommandTest
from ..models import Job


class DeleteJobTest(ManagementCommandTest):

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()

    def test_delete(self):
        job_1 = Job(job_name='1')
        job_1.save()
        job_2 = Job(job_name='2')
        job_2.save()
        job_3 = Job(job_name='3')
        job_3.save()

        stdout_text, _ = self.call_command_and_get_output(
            'jobs', 'delete_job', args=[job_1.pk, job_3.pk])
        self.assertIn(
            f"The 2 specified Job(s) have been deleted.",
            stdout_text)

        job_names = {
            job.job_name for job in Job.objects.all()
        }
        self.assertSetEqual(
            job_names, {'2'}, "Only job 2 should remain",
        )
