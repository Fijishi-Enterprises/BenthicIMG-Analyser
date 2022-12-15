from datetime import timedelta

from bs4 import BeautifulSoup
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from api_core.models import ApiJob, ApiJobUnit
from lib.tests.utils import BasePermissionTest, ClientTest, HtmlTestMixin
from ..models import Job
from ..utils import queue_job
from .utils import queue_job_with_modify_date


class PermissionTest(BasePermissionTest):

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()

        cls.img = cls.upload_image(cls.user, cls.source)

    def test_overall_dashboard(self):
        url = reverse('jobs:overall_dashboard')
        template = 'jobs/overall_dashboard.html'

        self.assertPermissionLevel(
            url, self.SUPERUSER, template=template,
            deny_type=self.REQUIRE_LOGIN)

    def test_source_dashboard(self):
        url = reverse('jobs:source_dashboard', args=[self.source.pk])
        template = 'jobs/source_dashboard.html'

        self.source_to_private()
        self.assertPermissionLevel(url, self.SOURCE_EDIT, template=template)
        self.source_to_public()
        self.assertPermissionLevel(url, self.SOURCE_EDIT, template=template)


class AdminDashboardTest(ClientTest, HtmlTestMixin):

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()

        cls.user = cls.create_user()
        cls.source = cls.create_source(cls.user, name="Source 1")
        cls.sources = [
            cls.source,
            cls.create_source(cls.user, name="Source 2"),
            cls.create_source(cls.user, name="Source 3"),
            cls.create_source(cls.user, name="Source 4"),
            cls.create_source(cls.user, name="Source 5"),
            cls.create_source(cls.user, name="Source 6"),
        ]

        cls.url = reverse('jobs:overall_dashboard')
        cls.source_url = reverse(
            'jobs:source_dashboard', args=[cls.source.pk])
        cls.source_urls = [
            cls.source_url,
            reverse('jobs:source_dashboard', args=[cls.sources[1].pk]),
            reverse('jobs:source_dashboard', args=[cls.sources[2].pk]),
            reverse('jobs:source_dashboard', args=[cls.sources[3].pk]),
            reverse('jobs:source_dashboard', args=[cls.sources[4].pk]),
            reverse('jobs:source_dashboard', args=[cls.sources[5].pk]),
        ]

    def assert_non_source_summary_equal(self, response_soup, expected_numbers):
        non_source_summary_p = response_soup.select('p#non-source-summary')[0]
        n1, n2, n3 = expected_numbers
        self.assertHTMLEqual(
            non_source_summary_p.text,
            f"Non-source jobs: {n1} in progress, {n2} pending,"
            f" {n3} completed in last 3 days",
            "Summary of non-source jobs is as expected")

    def test_no_jobs(self):
        """Just testing that this doesn't get an error."""
        self.client.force_login(self.superuser)
        response = self.client.get(self.url)
        self.assertStatusOK(response)

    def test_source_jobs_only(self):
        queue_job('1', source_id=self.source.pk, initial_status=Job.PENDING)
        queue_job('2', source_id=self.source.pk, initial_status=Job.PENDING)
        queue_job('3', source_id=self.source.pk, initial_status=Job.IN_PROGRESS)
        queue_job('4', source_id=self.source.pk, initial_status=Job.SUCCESS)
        queue_job('5', source_id=self.source.pk, initial_status=Job.SUCCESS)
        queue_job('6', source_id=self.source.pk, initial_status=Job.FAILURE)

        self.client.force_login(self.superuser)
        response = self.client.get(self.url)
        response_soup = BeautifulSoup(response.content, 'html.parser')

        rows = response_soup.select(
            'table#sources-with-jobs > tbody > tr')
        self.assert_soup_tr_contents_equal(
            rows[0],
            [f'<a href="{self.source_url}">Source 1</a>', 1, 2, 3])
        self.assert_non_source_summary_equal(response_soup, [0, 0, 0])

    def test_non_source_jobs_only(self):
        queue_job('1', initial_status=Job.PENDING)
        queue_job('2', initial_status=Job.PENDING)
        queue_job('3', initial_status=Job.IN_PROGRESS)
        queue_job('4', initial_status=Job.SUCCESS)
        queue_job('5', initial_status=Job.SUCCESS)
        queue_job('6', initial_status=Job.FAILURE)

        self.client.force_login(self.superuser)
        response = self.client.get(self.url)
        response_soup = BeautifulSoup(response.content, 'html.parser')

        rows = response_soup.select(
            'table#sources-with-jobs > tbody > tr')
        self.assertEqual(len(rows), 0, "Source table should be empty")
        self.assert_non_source_summary_equal(response_soup, [1, 2, 3])

    def test_source_and_non_source_jobs(self):
        queue_job('1', source_id=self.source.pk, initial_status=Job.PENDING)
        queue_job('2', initial_status=Job.PENDING)

        self.client.force_login(self.superuser)
        response = self.client.get(self.url)
        response_soup = BeautifulSoup(response.content, 'html.parser')

        rows = response_soup.select(
            'table#sources-with-jobs > tbody > tr')
        self.assert_soup_tr_contents_equal(
            rows[0],
            [f'<a href="{self.source_url}">Source 1</a>', 0, 1, 0])
        self.assert_non_source_summary_equal(response_soup, [0, 1, 0])

    def test_source_ordering(self):
        # 3rd: has pending, modified later
        queue_job_with_modify_date(
            '1', source_id=self.sources[0].pk, initial_status=Job.PENDING,
            modify_date=timezone.now() + timedelta(days=1))
        queue_job(
            '2', source_id=self.sources[0].pk, initial_status=Job.SUCCESS)
        # 4th: has pending
        queue_job(
            '3', source_id=self.sources[1].pk, initial_status=Job.PENDING)
        queue_job(
            '4', source_id=self.sources[1].pk, initial_status=Job.PENDING)

        # 2nd: has in progress
        queue_job(
            '5', source_id=self.sources[2].pk, initial_status=Job.IN_PROGRESS)
        queue_job(
            '6', source_id=self.sources[2].pk, initial_status=Job.SUCCESS)
        # 1st: has in progress, modified later
        queue_job_with_modify_date(
            '7', source_id=self.sources[3].pk, initial_status=Job.IN_PROGRESS,
            modify_date=timezone.now() + timedelta(days=1))
        queue_job(
            '8', source_id=self.sources[3].pk, initial_status=Job.PENDING)

        # 5th: only has completed, modified later
        queue_job(
            '9', source_id=self.sources[4].pk, initial_status=Job.SUCCESS)
        queue_job_with_modify_date(
            '10', source_id=self.sources[4].pk, initial_status=Job.SUCCESS,
            modify_date=timezone.now() + timedelta(days=1))
        # 6th: only has completed
        queue_job(
            '11', source_id=self.sources[5].pk, initial_status=Job.SUCCESS)
        queue_job(
            '12', source_id=self.sources[5].pk, initial_status=Job.SUCCESS)

        self.client.force_login(self.superuser)
        response = self.client.get(self.url)
        response_soup = BeautifulSoup(response.content, 'html.parser')

        rows = response_soup.select(
            'table#sources-with-jobs > tbody > tr')
        self.assert_soup_tr_contents_equal(
            rows[0],
            [f'<a href="{self.source_urls[3]}">Source 4</a>', 1, 1, 0])
        self.assert_soup_tr_contents_equal(
            rows[1],
            [f'<a href="{self.source_urls[2]}">Source 3</a>', 1, 0, 1])
        self.assert_soup_tr_contents_equal(
            rows[2],
            [f'<a href="{self.source_urls[0]}">Source 1</a>', 0, 1, 1])
        self.assert_soup_tr_contents_equal(
            rows[3],
            [f'<a href="{self.source_urls[1]}">Source 2</a>', 0, 2, 0])
        self.assert_soup_tr_contents_equal(
            rows[4],
            [f'<a href="{self.source_urls[4]}">Source 5</a>', 0, 0, 2])
        self.assert_soup_tr_contents_equal(
            rows[5],
            [f'<a href="{self.source_urls[5]}">Source 6</a>', 0, 0, 2])

    def test_source_job_age_cutoff(self):
        # Not old enough to clean up
        queue_job_with_modify_date(
            '1', source_id=self.sources[0].pk, initial_status=Job.SUCCESS,
            modify_date=timezone.now() - timedelta(days=2, hours=23))

        # Old enough to clean up
        queue_job_with_modify_date(
            '2', source_id=self.sources[1].pk, initial_status=Job.SUCCESS,
            modify_date=timezone.now() - timedelta(days=3, hours=1))

        # Old enough to clean up, but pending
        queue_job_with_modify_date(
            '3', source_id=self.sources[2].pk, initial_status=Job.PENDING,
            modify_date=timezone.now() - timedelta(days=3, hours=1))

        # Old enough to clean up, but in progress
        queue_job_with_modify_date(
            '4', source_id=self.sources[3].pk, initial_status=Job.IN_PROGRESS,
            modify_date=timezone.now() - timedelta(days=3, hours=1))

        self.client.force_login(self.superuser)
        response = self.client.get(self.url)
        response_soup = BeautifulSoup(response.content, 'html.parser')

        # Should be missing source 2
        rows = response_soup.select(
            'table#sources-with-jobs > tbody > tr')
        self.assertEqual(len(rows), 3)
        self.assert_soup_tr_contents_equal(
            rows[0],
            [f'<a href="{self.source_urls[3]}">Source 4</a>', 1, 0, 0])
        self.assert_soup_tr_contents_equal(
            rows[1],
            [f'<a href="{self.source_urls[2]}">Source 3</a>', 0, 1, 0])
        self.assert_soup_tr_contents_equal(
            rows[2],
            [f'<a href="{self.source_urls[0]}">Source 1</a>', 0, 0, 1])

    def test_non_source_job_age_cutoff(self):
        # Not old enough to clean up
        queue_job_with_modify_date(
            '1', initial_status=Job.SUCCESS,
            modify_date=timezone.now() - timedelta(days=2, hours=23))

        # Old enough to clean up
        queue_job_with_modify_date(
            '2', initial_status=Job.SUCCESS,
            modify_date=timezone.now() - timedelta(days=3, hours=1))

        # Old enough to clean up, but pending
        queue_job_with_modify_date(
            '3', initial_status=Job.PENDING,
            modify_date=timezone.now() - timedelta(days=3, hours=1))

        # Old enough to clean up, but in progress
        queue_job_with_modify_date(
            '4', initial_status=Job.IN_PROGRESS,
            modify_date=timezone.now() - timedelta(days=3, hours=1))

        self.client.force_login(self.superuser)
        response = self.client.get(self.url)
        response_soup = BeautifulSoup(response.content, 'html.parser')

        # Should only show 1 pending
        self.assert_non_source_summary_equal(response_soup, [1, 1, 1])


class SourceDashboardTest(ClientTest, HtmlTestMixin):

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()

        cls.user = cls.create_user()
        cls.source = cls.create_source(cls.user, name="Source 1")
        cls.source_url = reverse(
            'jobs:source_dashboard', args=[cls.source.pk])

    @override_settings(JOB_MAX_DAYS=30)
    def test_no_jobs(self):
        self.client.force_login(self.user)
        response = self.client.get(self.source_url)
        self.assertContains(response, "(No jobs found)")
        self.assertContains(
            response,
            "Most job records are cleaned up after 30 days,"
            " except for jobs with * in Last updated.")

    def test_job_ordering(self):
        # 3rd: pending, modified later
        job_1 = queue_job_with_modify_date(
            '1', source_id=self.source.pk, initial_status=Job.PENDING,
            modify_date=timezone.now() + timedelta(days=1))
        # 4th: pending
        job_2 = queue_job(
            '2', source_id=self.source.pk, initial_status=Job.PENDING)

        # 2nd: in progress
        job_3 = queue_job(
            '3', source_id=self.source.pk, initial_status=Job.IN_PROGRESS)
        # 1st: in progress, modified later
        job_4 = queue_job_with_modify_date(
            '4', source_id=self.source.pk, initial_status=Job.IN_PROGRESS,
            modify_date=timezone.now() + timedelta(days=1))

        # 6th: completed, modified 2nd latest (success/failure doesn't matter)
        job_5 = queue_job_with_modify_date(
            '5', source_id=self.source.pk, initial_status=Job.FAILURE,
            modify_date=timezone.now() + timedelta(days=1))
        # 7th: completed
        job_6 = queue_job(
            '6', source_id=self.source.pk, initial_status=Job.SUCCESS)
        # 5th: completed, modified latest
        job_7 = queue_job_with_modify_date(
            '7', source_id=self.source.pk, initial_status=Job.SUCCESS,
            modify_date=timezone.now() + timedelta(days=2))

        self.client.force_login(self.user)
        response = self.client.get(self.source_url)
        response_soup = BeautifulSoup(response.content, 'html.parser')

        rows = response_soup.select(
            'table#jobs-table > tbody > tr')
        self.assert_soup_tr_contents_equal(
            rows[0],
            [job_4.pk, '4', '', "In progress", None, None])
        self.assert_soup_tr_contents_equal(
            rows[1],
            [job_3.pk, '3', '', "In progress", None, None])
        self.assert_soup_tr_contents_equal(
            rows[2],
            [job_1.pk, '1', '', "Pending", None, None])
        self.assert_soup_tr_contents_equal(
            rows[3],
            [job_2.pk, '2', '', "Pending", None, None])
        self.assert_soup_tr_contents_equal(
            rows[4],
            [job_7.pk, '7', '', "Success", None, None])
        self.assert_soup_tr_contents_equal(
            rows[5],
            [job_5.pk, '5', '', "Failure", None, None])
        self.assert_soup_tr_contents_equal(
            rows[6],
            [job_6.pk, '6', '', "Success", None, None])

    def test_image_id_column(self):
        queue_job('extract_features', '1', source_id=self.source.pk)
        queue_job('train_classifier', '2', source_id=self.source.pk)
        queue_job('classify_features', '3', source_id=self.source.pk)

        self.client.force_login(self.user)
        response = self.client.get(self.source_url)
        response_soup = BeautifulSoup(response.content, 'html.parser')

        image_3_url = reverse('image_detail', args=['3'])
        image_1_url = reverse('image_detail', args=['1'])

        # Should only fill the image ID cell for specific job names
        rows = response_soup.select(
            'table#jobs-table > tbody > tr')
        self.assert_soup_tr_contents_equal(
            rows[0],
            [None, "Classify", f'<a href="{image_3_url}">3</a>',
             "Pending", None, None])
        self.assert_soup_tr_contents_equal(
            rows[1],
            [None, "Train classifier", '', "Pending", None, None])
        self.assert_soup_tr_contents_equal(
            rows[2],
            [None, "Extract features", f'<a href="{image_1_url}">1</a>',
             "Pending", None, None])

    def test_result_message_column(self):
        queue_job(
            '1', source_id=self.source.pk, initial_status=Job.SUCCESS)

        job = queue_job(
            '2', source_id=self.source.pk, initial_status=Job.FAILURE)
        job.result_message = "Error message goes here"
        job.save()

        job = queue_job(
            '3', source_id=self.source.pk, initial_status=Job.SUCCESS)
        job.result_message = "Comment about the result goes here"
        job.save()

        self.client.force_login(self.user)
        response = self.client.get(self.source_url)
        response_soup = BeautifulSoup(response.content, 'html.parser')

        rows = response_soup.select(
            'table#jobs-table > tbody > tr')
        self.assert_soup_tr_contents_equal(
            rows[0],
            [None, '3', None,
             None, "Comment about the result goes here", None])
        self.assert_soup_tr_contents_equal(
            rows[1],
            [None, '2', None,
             None, "Error message goes here", None])
        self.assert_soup_tr_contents_equal(
            rows[2],
            [None, '1', None,
             None, "", None])

    def test_persist_marker(self):
        job = queue_job('1', source_id=self.source.pk)
        job.persist = True
        job.save()
        queue_job('2', source_id=self.source.pk)

        self.client.force_login(self.user)
        response = self.client.get(self.source_url)
        response_soup = BeautifulSoup(response.content, 'html.parser')

        # First row ('2') should not have *, second row ('1') should
        rows = response_soup.select(
            'table#jobs-table > tbody > tr')
        self.assertNotIn('*', str(rows[0]))
        self.assertIn('*', str(rows[1]))

    @override_settings(JOBS_PER_PAGE=2)
    def test_multiple_pages(self):
        queue_job('1', source_id=self.source.pk)
        queue_job('2', source_id=self.source.pk)
        queue_job('3', source_id=self.source.pk)
        queue_job('4', source_id=self.source.pk)
        queue_job('5', source_id=self.source.pk)
        queue_job('6', source_id=self.source.pk)
        queue_job('7', source_id=self.source.pk)

        self.client.force_login(self.user)

        for page, expected_row_count in [(1, 2), (2, 2), (3, 2), (4, 1)]:
            response = self.client.get(
                self.source_url, data=dict(page=page))
            response_soup = BeautifulSoup(response.content, 'html.parser')

            rows = response_soup.select(
                'table#jobs-table > tbody > tr')
            self.assertEqual(len(rows), expected_row_count)

    def test_exclude_check_source_from_table(self):
        queue_job('check_source', '1', source_id=self.source.pk)
        queue_job('classify_features', '2', source_id=self.source.pk)

        self.client.force_login(self.user)
        response = self.client.get(self.source_url)
        response_soup = BeautifulSoup(response.content, 'html.parser')

        # Should only show the classify_features job
        rows = response_soup.select(
            'table#jobs-table > tbody > tr')
        self.assertEqual(len(rows), 1)
        self.assert_soup_tr_contents_equal(
            rows[0],
            [None, "Classify", None, None, None, None])

    def test_check_source_message(self):
        # No recent source check
        self.client.force_login(self.user)
        response = self.client.get(self.source_url)
        self.assertContains(
            response, "This source hasn't been status-checked recently.")

        # Add source check jobs for the source
        job = queue_job(
            'check_source', self.source.pk, source_id=self.source.pk,
            initial_status=Job.SUCCESS)
        job.result_message = "Message 1"
        job.save()
        job = queue_job(
            'check_source', self.source.pk, source_id=self.source.pk,
            initial_status=Job.SUCCESS)
        job.result_message = "Message 2"
        job.save()
        job = queue_job(
            'check_source', self.source.pk, source_id=self.source.pk,
            initial_status=Job.IN_PROGRESS)
        job.save()

        # Most recent completed source check
        response = self.client.get(self.source_url)
        self.assertContains(
            response, '<em>Latest source check result:</em> Message 2')


class NonSourceDashboardTest(ClientTest, HtmlTestMixin):

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()

        cls.user = cls.create_user()
        cls.source = cls.create_source(cls.user)
        cls.url = reverse('jobs:non_source_dashboard')

    def test_api_job_unit_column(self):
        queue_job('Some job', '1', '2')

        job = queue_job('classify_image', '3', '4')
        api_job = ApiJob(type='deploy', user=self.user)
        api_job.save()
        api_job_unit = ApiJobUnit(
            parent=api_job, order_in_parent=1, internal_job=job,
            request_json={})
        api_job_unit.save()

        self.client.force_login(self.superuser)
        response = self.client.get(self.url)
        response_soup = BeautifulSoup(response.content, 'html.parser')

        api_job_url = reverse('api_management:job_detail', args=[api_job.pk])

        # Should only fill the API job unit cell for deploy
        rows = response_soup.select(
            'table#jobs-table > tbody > tr')
        self.assert_soup_tr_contents_equal(
            rows[0],
            [None, "Deploy", f'<a href="{api_job_url}">{api_job_unit.pk}</a>',
             None, None, None])
        self.assert_soup_tr_contents_equal(
            rows[1],
            [None, 'Some job', '', None, None, None])
