from abc import ABC
from typing import Literal

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.shortcuts import get_object_or_404, render
from django.utils.decorators import method_decorator
from django.views import View

from images.models import Source
from lib.decorators import source_permission_required
from lib.utils import paginate
from .forms import JobSearchForm, JobSummaryForm
from .models import Job


def tag_to_readable(tag):
    return tag.capitalize().replace('_', ' ')


class JobDashboardView(View, ABC):
    source_id: int | None | Literal['all']
    template_name: str
    form: JobSearchForm = None

    def get(self, request, **kwargs):
        if request.GET:
            self.form = JobSearchForm(request.GET, source_id=self.source_id)
            if not self.form.is_valid():
                messages.error(request, "Please correct the errors below.")
                context = dict(job_search_form=self.form)
                return render(request, self.template_name, context)
        else:
            self.form = JobSearchForm(source_id=self.source_id)

        context = dict(job_search_form=self.form)
        context |= self.context_if_valid(request)

        return render(request, self.template_name, context)

    def context_if_valid(self, request):
        raise NotImplementedError

    def get_job_list_context(self, request, jobs, job_counts):
        has_source_column = self.source_id == 'all'
        page_jobs, query_string = paginate(
            results=jobs,
            items_per_page=settings.JOBS_PER_PAGE,
            request_args=request.GET,
        )

        job_table = []

        fields = [
            'pk', 'job_name', 'arg_identifier',
            'apijobunit', 'apijobunit__parent',
            'status', 'result_message', 'persist', 'modify_date',
        ]
        if has_source_column:
            fields += ['source', 'source__name']

        status_choices_labels = dict(Job.Status.choices)

        for values in page_jobs.object_list.values(*fields):
            table_entry = dict(
                id=values['pk'],
                status=values['status'],
                status_display=status_choices_labels[values['status']],
                result_message=values['result_message'],
                persist=values['persist'],
                modify_date=values['modify_date'],
            )

            if has_source_column:
                table_entry['source_id'] = values['source']
                table_entry['source_name'] = values['source__name']

            if values['job_name'] == 'classify_image':
                table_entry['job_type'] = "Deploy"
            if values['job_name'] == 'classify_features':
                table_entry['job_type'] = "Classify"
            else:
                table_entry['job_type'] = tag_to_readable(values['job_name'])

            if values['job_name'] == 'classify_image':
                table_entry['api_job_unit_id'] = values['apijobunit']
                table_entry['api_job_id'] = values['apijobunit__parent']
            if values['job_name'] in [
                'extract_features', 'classify_features'
            ]:
                table_entry['image_id'] = values['arg_identifier']

            job_table.append(table_entry)

        return dict(
            page_results=page_jobs,
            query_string=query_string,
            job_table=job_table,
            job_max_days=settings.JOB_MAX_DAYS,
            job_counts=job_counts,
        )

    def get_source_context(self):
        source = get_object_or_404(Source, id=self.source_id)

        try:
            latest_check = source.job_set.filter(
                job_name='check_source',
                status__in=[
                    Job.Status.SUCCESS,
                    Job.Status.FAILURE,
                    Job.Status.IN_PROGRESS,
                ]
            ).latest('pk')
            check_in_progress = (latest_check.status == Job.Status.IN_PROGRESS)
        except Job.DoesNotExist:
            latest_check = None
            check_in_progress = False

        return dict(
            source=source,
            latest_check=latest_check,
            check_in_progress=check_in_progress,
        )


@method_decorator(
    permission_required('is_superuser'),
    name='dispatch')
class AllJobsListView(JobDashboardView):
    """List of all jobs: from any source or no source."""
    source_id = 'all'
    template_name = 'jobs/all_jobs_list.html'

    def context_if_valid(self, request):
        return self.get_job_list_context(
            request, self.form.get_jobs(), self.form.get_job_counts()
        )


# @dataclass(kw_only=True)
@method_decorator(
    source_permission_required('source_id', perm=Source.PermTypes.EDIT.code),
    name='dispatch')
class SourceJobListView(JobDashboardView):
    """
    List of jobs from a specific source.
    """
    source_id: int
    template_name = 'jobs/source_job_list.html'

    def dispatch(self, *args, **kwargs):
        self.source_id = self.kwargs['source_id']
        return super().dispatch(*args, **kwargs)

    def context_if_valid(self, request):
        context = (
            self.get_job_list_context(
                request, self.form.get_jobs(), self.form.get_job_counts()
            )
            | self.get_source_context()
        )
        return context


@method_decorator(
    permission_required('is_superuser'),
    name='dispatch')
class NonSourceJobListView(JobDashboardView):
    """
    List of jobs not belonging to a source.
    """
    source_id = None
    template_name = 'jobs/non_source_job_list.html'

    def context_if_valid(self, request):
        return self.get_job_list_context(
            request, self.form.get_jobs(), self.form.get_job_counts()
        )


@method_decorator(
    permission_required('is_superuser'),
    name='dispatch')
class JobSummaryView(View):
    """
    Top-level dashboard for monitoring jobs.
    """
    template_name = 'jobs/all_jobs_summary.html'

    def get(self, request, **kwargs):
        if request.GET:
            summary_form = JobSummaryForm(request.GET)
            if not summary_form.is_valid():
                messages.error(request, "Please correct the errors below.")
                context = dict(job_summary_form=summary_form)
                return render(request, self.template_name, context)
        else:
            summary_form = JobSummaryForm()

        job_counts_by_source, non_source_job_counts = \
            summary_form.get_job_counts_by_source()

        context = dict(
            job_summary_form=summary_form,
            source_table=job_counts_by_source,
            overall_job_counts=summary_form.get_job_counts(),
            non_source_job_counts=non_source_job_counts,
            completed_day_limit=summary_form.completed_day_limit,
        )

        return render(request, self.template_name, context)
