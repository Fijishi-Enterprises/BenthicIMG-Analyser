from lib.tests.utils import ManagementCommandTest
from ..models import Job


class AbortJobTest(ManagementCommandTest):

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()

    def test_abort(self):
        job_1 = Job(job_name='1')
        job_1.save()
        job_2 = Job(job_name='2')
        job_2.save()
        job_3 = Job(job_name='3')
        job_3.save()

        stdout_text, _ = self.call_command_and_get_output(
            'jobs', 'abort_job', args=[job_1.pk, job_3.pk])
        self.assertIn(
            f"The 2 specified Job(s) have been aborted.",
            stdout_text)

        job_details = {
            (job.job_name, job.status, job.result_message)
            for job in Job.objects.all()
        }
        self.assertSetEqual(
            job_details,
            {
                ('1', Job.Status.FAILURE, "Aborted manually"),
                ('2', Job.Status.PENDING, ""),
                ('3', Job.Status.FAILURE, "Aborted manually"),
            },
            "Only jobs 1 and 3 should have been aborted",
        )
