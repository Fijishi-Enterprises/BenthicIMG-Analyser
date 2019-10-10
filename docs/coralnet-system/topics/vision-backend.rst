Computer Vision Backend
==========================================================================================

Install
----------
To install required python packages (if you haven't already), simply use (This installs a bunch of prereqs also):

``pip install celery[redis]``

You also need to install the actual redis program with is a message broker. On mac, for example, use:

``brew install redis``

On Ubuntu 16.04:

``sudo apt-get install redis-server``

OPTIONAL. You can also install "flower" which is a neat celery task viewer. Again, reqs. are in requirements/base.txt, but you can simply install with:

``pip install flower``

Also, the backend requires Django settings that use S3 media storage, not local media storage.

Run (simple)
--------------------
You then need to run the following commands (in seperate consoles). Run them all from the project root (where manage.py is).

Start the redis message:

``redis-server``

Start the celery worker process which will consume the jobs:

``celery -A config worker``

Starts the scheduler which will create tasks decorated with @periodic_task:

``celery -A config beat``

OPTIONAL. This runs the celery task viewer:

``celery flower -A config``

Run (production)
--------------------
For production we use a service called supervisord. Supervisord allows celery beat and worker to be run as daemons in the background.

This can also easily be setup in development if desired. It works on Mac, Linux, and `Cygwin <http://stackoverflow.com/a/18032347/>`__.

To install use (this is included in the base requirements):

``pip install supervisor``

To start supervisor go to the project home (where manage.py lives) and type

``supervisord -c config/supervisor.conf``

That is it! Now you can use the supervisorctl utility like so:

``supervisorctl -c config/supervisor.conf status``

Try, for example

``supervisorctl -c config/supervisor.conf stop celeryworker``

``supervisorctl -c config/supervisor.conf start celeryworker``

Regression-tests
--------------------
CoralNet vision regression-tests can be run through as management command. Fixtures are stored in the "coralnet-regtest-fixtures" S3 bucket. 

``python manage.py vb_regtests``

There are only three options

python manage.py vision_backed_regtests {small, medium, large}

which runs regtests of different sizes for the two sources in the fixtures.

**Warning, the regression tests will create source directly in your database. You need to create a separate database instance for regression tests. This is suppored by the config files.**

Other management commands
------------------------------

``python manage.py vb_submit_features``

Can be used to submit feature extract jobs for images already uploaded to the site, but not processed for whatever reason.

``python manage.py read_spacer_errors``

This reads all messages in the spacer error queue and dumps the content to the console. Messages are deleted after they are processed.
