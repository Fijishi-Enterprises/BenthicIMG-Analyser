from django.urls import reverse

from api_core.models import ApiJob
from lib.tests.utils import ManagementCommandTest


class SubmitDeployTest(ManagementCommandTest):

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.user = cls.create_user()
        cls.source = cls.create_source(cls.user)
        cls.classifier = cls.create_robot(cls.source)

    def test_success(self):
        stdout_text, _ = self.call_command_and_get_output(
            'vision_backend_api', 'submit_deploy',
            args=[
                self.user.username,
                self.classifier.pk,
                'A URL',
            ],
        )

        api_job = ApiJob.objects.latest('pk')
        api_job_unit = api_job.apijobunit_set.all()[0]
        self.assertEqual(
            api_job_unit.request_json['url'], 'A URL',
            "Expected URL should be assigned to the job unit")

        status_dashboard_url = reverse(
            'api_management:job_detail', args=[api_job.pk])
        self.assertIn(
            f"Deploy request sent. Check status here: {status_dashboard_url}",
            stdout_text)

    def test_error(self):
        # Use a nonexistent classifier ID
        classifier_id = self.classifier.pk
        self.classifier.delete()

        stdout_text, _ = self.call_command_and_get_output(
            'vision_backend_api', 'submit_deploy',
            args=[
                self.user.username,
                classifier_id,
                'A URL',
            ],
        )

        self.assertIn(
            f"Error: This classifier doesn't exist or is not accessible",
            stdout_text)
