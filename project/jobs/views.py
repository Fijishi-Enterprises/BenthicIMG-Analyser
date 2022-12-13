from collections import Counter, defaultdict
from datetime import timedelta

from django.contrib.auth.decorators import permission_required
from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from images.models import Source
from lib.decorators import source_permission_required
from .models import Job


@permission_required('is_superuser')
def admin_dashboard(request):
    """
    Admin dashboard for monitoring jobs.
    """
    now = timezone.now()

    # check_source jobs generally clutter the dashboard more than they provide
    # useful info.
    jobs = Job.objects.exclude(
        job_name='check_source').order_by('-modify_date')

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

    return render(request, 'jobs/admin_dashboard.html', {
        'source_table': source_table,
        'non_source_job_counts': non_source_job_counts,
        'completed_days_shown': COMPLETED_DAYS_SHOWN,
    })


@source_permission_required('source_id', perm=Source.PermTypes.EDIT.code)
def source_dashboard(request, source_id):
    source = get_object_or_404(Source, id=source_id)

    now = timezone.now()

    jobs = source.job_set.exclude(
        job_name='check_source').order_by('-modify_date')

    COMPLETED_DAYS_SHOWN = 3
    in_progress_jobs = jobs.filter(status=Job.IN_PROGRESS)
    pending_jobs = jobs.filter(status=Job.PENDING)
    completed_jobs = jobs.filter(
        status__in=[Job.SUCCESS, Job.FAILURE],
        modify_date__gt=now - timedelta(days=COMPLETED_DAYS_SHOWN))

    def tag_to_readable(tag):
        return tag.capitalize().replace('_', ' ')

    job_table = []
    for group_status, job_group in [
        ('in_progress', in_progress_jobs),
        ('pending', pending_jobs),
        ('completed', completed_jobs),
    ]:
        for values in job_group.values(
            'pk', 'create_date', 'modify_date', 'job_name',
            'arg_identifier', 'status',
        ):
            if group_status == 'completed':
                # Should report as success or failure.
                if values['status'] == Job.SUCCESS:
                    status_tag = 'success'
                else:
                    status_tag = 'failure'
            else:
                # This ensures that jobs which changed status milliseconds ago
                # won't have a mismatch between group_status and status_tag.
                status_tag = group_status

            table_entry = dict(
                status_tag=status_tag,
                status=tag_to_readable(status_tag),
                id=values['pk'],
                modify_date=values['modify_date'],
                create_date=values['create_date'],
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

    return render(request, 'jobs/source_dashboard.html', {
        'source': source,
        'job_table': job_table,
        'completed_days_shown': COMPLETED_DAYS_SHOWN,
    })
