# Changelog

## 1.4

- Updates to required packages:
  - Removed `celery`.
  - Removed celery dependencies `amqp`, `anyjson`, `billiard`, and `kombu`.
  - Added `huey>=2.4.4,<2.5`.
  - Updated `redis==2.10.5` to `redis>=4.3.5,<4.4`.
- ``CELERY_ALWAYS_EAGER`` setting has been replaced with ``HUEY['immediate']``.
- Feel free to clean up any celery-generated files, such as the logs and schedule.

## 1.3

- Updates to required packages:
  - Removed `boto`.
  - Added `boto3==1.23.10`.

## 1.2

**Before updating from 1.1 to 1.2,** ensure that all spacer jobs and BatchJobs have finished first, because 1) spacer job token formats have changed for train and deploy, and 2) the migrations will be abandoning all existing BatchJobs. To do this:
  - Stop the web server and celery processes.
  - If using BatchQueue, check the AWS Batch console to ensure all your BatchJobs have finished. If using LocalQueue, then no waiting is needed here.
  - Manually run `collect_all_jobs()` in the shell to collect those jobs.

Once that's done, update to 1.2, then:

- Run migrations for ``api_core``, ``jobs`` (new app), and ``vision_backend``. Expect moderate runtime to process existing BatchJobs.

- Do an announcement after updating production. The new job-monitoring page for sources will hopefully answer many questions of the form "what's happening with the classifiers in my source?".

## 1.1

Update instructions have not been well tracked up to this point. If the migrations give you trouble, consider starting your environment fresh from 1.2 or later.

## 1.0

See [blog post](https://coralnet.ucsd.edu/blog/coralnet-is-officially-out-of-beta/) for major changes associated with this release.