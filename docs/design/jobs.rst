Asynchronous jobs
=================


Why we switched from celery to huey - from `PR #464 <https://github.com/coralnet/coralnet/pull/464>`__:

  Long story short, I was trying to update celery (issue #310) from 3.1.23 to 5.1.2 (latest version that supports Python 3.6). I was able to get over some hurdles, but got really stuck on this error, which appeared in the celery output whenever it tried to run a periodic task:

  ::

    [2023-01-06 15:20:24,721: ERROR/MainProcess] Task handler raised error: ValueError('not enough values to unpack (expected 3, got 0)',)
    Traceback (most recent call last):
      File "...\site-packages\billiard\pool.py", line 362, in workloop
        result = (True, prepare_result(fun(*args, **kwargs)))
      File "...\site-packages\celery\app\trace.py", line 635, in fast_trace_task
        tasks, accept, hostname = _loc
    ValueError: not enough values to unpack (expected 3, got 0)

  At this point, I was already considering that celery might be more heavyweight than our use case demands (e.g. basically being 3 packages in one: celery, billiard, kombu), so I looked at alternatives and ended up trying huey.

We essentially use huey for two things:

- Scheduling just a couple of 'bootstrap' periodic jobs (the other periodic jobs are managed by coralnet's code).

- Managing the separate processes/threads which actually run the asynchronous jobs.

Most periodic jobs are queued up by coralnet's code (starting in PR #480) because:

- This makes it easier for us to check when the next scheduled run of a job will be; it doesn't seem straightforward to check this when the periodic jobs are managed by huey or celery.

- This makes it less likely for infrequent periodic jobs to be skipped for a while, since huey would skip a job's turn if huey was busy for the specific minute that the job was scheduled for.

Note that the coralnet-managed periodic jobs define an interval from the end of one run to the start of the next run. In contrast, huey defines an interval from the start of one run to the start of the next run.

No alternatives besides celery and huey were actually tried yet, so it's possible that something else would work better still. Non-ideal points of huey known thus far:

- To check the next scheduled run of a periodic job, need to solve the problem of "given a crontab specification, when is it going to run next?", which is tricky to implement in a less brute-force fashion than "iterate over every possible minute until we find a match".

- Skips a job's turn if huey was busy for the specific minute that the job was scheduled for (e.g. 0:00 if it's a daily job with no offset).

- It's not easy for tasks to define their own "graceful shutdown" behavior: https://github.com/coleifer/huey/issues/743 (As a result, we instead try to limit the maximum amount of time that we'd expect a single task to run, and then supervisor can wait that amount of time between sending SIGINT and SIGKILL.)
