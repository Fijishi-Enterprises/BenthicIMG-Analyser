from collections import Counter, defaultdict
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.decorators import permission_required
from django.db.models.expressions import Case, Value, When
from django.db.models.fields import IntegerField
from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from images.models import Source
from lib.decorators import source_permission_required
from lib.utils import paginate
from .models import Job


@permission_required('is_superuser')
def overall_dashboard(request):
    """
    Top-level dashboard for monitoring jobs.
    """
    now = timezone.now()

    # check_source jobs generally clutter the dashboard more than they provide
    # useful info.
    jobs = Job.objects.exclude(
        job_name='check_source').order_by('-modify_date', '-id')

    COMPLETED_DAYS_SHOWN = 3
    in_progress_jobs = jobs.filter(status=Job.IN_PROGRESS)
    pending_jobs = jobs.filter(status=Job.PENDING)
    recently_completed_jobs = jobs.filter(
        status__in=[Job.SUCCESS, Job.FAILURE],
        modify_date__gt=now - timedelta(days=COMPLETED_DAYS_SHOWN))

    source_job_counts = defaultdict(dict)

    for status_tag, job_group in [
        ('in_progress', in_progress_jobs),
        ('pending', pending_jobs),
        ('recently_completed', recently_completed_jobs),
    ]:
        job_source_ids = job_group.values_list('source_id', flat=True)
        source_id_counts = Counter(job_source_ids)
        for source_id, count in source_id_counts.items():
            source_job_counts[source_id][status_tag] = count

    # Get stats for non-source jobs separately.
    non_source_job_counts = source_job_counts.pop(None, dict())

    source_ids = list(source_job_counts.keys())

    sources = Source.objects.filter(pk__in=source_ids)
    source_names = {
        d['pk']: d['name']
        for d in sources.values('pk', 'name')
    }

    source_table = []
    for source_id, job_status_counts in source_job_counts.items():
        table_entry = job_status_counts
        table_entry['source_id'] = source_id
        table_entry['source_name'] = source_names[source_id]
        source_table.append(table_entry)

    return render(request, 'jobs/overall_dashboard.html', {
        'source_table': source_table,
        'non_source_job_counts': non_source_job_counts,
        'completed_days_shown': COMPLETED_DAYS_SHOWN,
    })


def tag_to_readable(tag):
    return tag.capitalize().replace('_', ' ')


@source_permission_required('source_id', perm=Source.PermTypes.EDIT.code)
def source_dashboard(request, source_id):
    """
    Job dashboard for a specific source.
    """
    source = get_object_or_404(Source, id=source_id)

    jobs = (
        source.job_set
        # check_source jobs generally clutter the dashboard more than they
        # provide useful info. So they won't be in the main table at least.
        .exclude(job_name='check_source')
        # In-progress jobs first, then pending, then completed.
        # Tiebreak by modify date.
        .annotate(
            status_score=Case(
                When(status=Job.IN_PROGRESS, then=Value(1)),
                When(status=Job.PENDING, then=Value(2)),
                default=Value(3),
                output_field=IntegerField(),
            )
        )
        .order_by('status_score', '-modify_date', '-id')
    )

    page_jobs = paginate(
        results=jobs,
        items_per_page=settings.JOBS_PER_PAGE,
        request_args=request.GET,
    )

    job_table = []
    for values in page_jobs.object_list.values(
        'pk', 'job_name', 'arg_identifier',
        'status', 'result_message', 'persist', 'modify_date'
    ):
        if values['status'] == Job.IN_PROGRESS:
            status_tag = 'in_progress'
        elif values['status'] == Job.PENDING:
            status_tag = 'pending'
        elif values['status'] == Job.SUCCESS:
            status_tag = 'success'
        else:
            # Job.FAILURE
            status_tag = 'failure'

        table_entry = dict(
            id=values['pk'],
            status_tag=status_tag,
            status=tag_to_readable(status_tag),
            result_message=values['result_message'],
            persist=values['persist'],
            modify_date=values['modify_date'],
        )

        if values['job_name'] == 'classify_features':
            table_entry['job_type'] = "Classify"
        else:
            table_entry['job_type'] = tag_to_readable(values['job_name'])

        if values['job_name'] in [
            'extract_features', 'classify_features'
        ]:
            table_entry['image_id'] = values['arg_identifier']

        job_table.append(table_entry)

    try:
        latest_completed_check = source.job_set.filter(
            job_name='check_source',
            status__in=[Job.SUCCESS, Job.FAILURE]).latest('pk')
        latest_source_check_message = latest_completed_check.result_message
    except Job.DoesNotExist:
        latest_source_check_message = None

    return render(request, 'jobs/source_dashboard.html', {
        'source': source,
        'job_table': job_table,
        'page_results': page_jobs,
        'job_max_days': settings.JOB_MAX_DAYS,
        'latest_source_check_message': latest_source_check_message,
    })


@permission_required('is_superuser')
def non_source_dashboard(request):
    """
    Dashboard for jobs not belonging to a specific source.
    """
    jobs = (
        Job.objects.filter(source__isnull=True)
        # In-progress jobs first, then pending, then completed.
        # Tiebreak by modify date.
        .annotate(
            status_score=Case(
                When(status=Job.IN_PROGRESS, then=Value(1)),
                When(status=Job.PENDING, then=Value(2)),
                default=Value(3),
                output_field=IntegerField(),
            )
        )
        .order_by('status_score', '-modify_date', '-id')
    )

    page_jobs = paginate(
        results=jobs,
        items_per_page=settings.JOBS_PER_PAGE,
        request_args=request.GET,
    )

    job_table = []
    for values in page_jobs.object_list.values(
        'pk', 'job_name', 'apijobunit', 'apijobunit__parent',
        'status', 'result_message', 'modify_date'
    ):
        if values['status'] == Job.IN_PROGRESS:
            status_tag = 'in_progress'
        elif values['status'] == Job.PENDING:
            status_tag = 'pending'
        elif values['status'] == Job.SUCCESS:
            status_tag = 'success'
        else:
            # Job.FAILURE
            status_tag = 'failure'

        table_entry = dict(
            id=values['pk'],
            status_tag=status_tag,
            status=tag_to_readable(status_tag),
            result_message=values['result_message'],
            modify_date=values['modify_date'],
        )

        if values['job_name'] == 'classify_image':
            table_entry['job_type'] = "Deploy"
        else:
            table_entry['job_type'] = tag_to_readable(values['job_name'])

        if values['job_name'] == 'classify_image':
            table_entry['api_job_unit_id'] = values['apijobunit']
            table_entry['api_job_id'] = values['apijobunit__parent']

        job_table.append(table_entry)

    return render(request, 'jobs/non_source_dashboard.html', {
        'job_table': job_table,
        'page_results': page_jobs,
        'job_max_days': settings.JOB_MAX_DAYS,
    })
