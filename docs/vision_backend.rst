.. _backend:

Installation, Setup, and Overview of the CoralNet vision backend
==========================================================================================

Async Task management system
------------------------------

Install
^^^^^^^^
To install requires python packages (if you haven't already), simply use (This installs a bunch of prereqs also):

- pip install celery[redis]

You also need to install the actual redis program with is a message broker. On mac, for example, use:

- brew install redis

On Ubuntu 16.04:

- sudo apt-get install redis-server

[Optional:]
You can also install "flower" which is a neat celery task viewer. Again, reqs. are in requirements/base.txt, but you can simply install with:

- pip install flower

Run
^^^^^^
You then need to run the following commands (in seperate consoles). Run them all from the project root (where manage.py is)

- redis server [This starts the redis message broker].

- celery -A config worker [This starts the celery worker process which will consume the jobs]

- celery -A config beat [This starts the scheduler which will create tasks decorated with @periodic_task.]

- celery flower -A config [OPTIONAL. This runs the celery task viewer.]



Unit-tests
^^^^^^^
The vision backend has a suite of "unit" tests. I use quotations since they are really too long and complicated to be designated as unit-tests. But nevertheless, for now, they will be run as part of the unit test suite.



Regression-tests
^^^^^^^^^^^^
CoralNet vision regression-tests can be run through as management command. Fixtures are stored in the "coralnet-regtest-fixtures" S3 bucket. 

python manage.py vision_backed_regtests -h

for help. There are only three options

python manage.py vision_backed_regtests {small, medium, large}

which runs regtests of different sizes for the two sources in the fixtures.
