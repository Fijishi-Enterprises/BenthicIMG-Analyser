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

On ubuntu, this will probably work:

- sudo apt-get install redis-server

[Optional:]
You can also install "flower" which is a neat celery task viewer. Again, reqs. are in requirements/base.txt, but you can simply install with:

- pip install flower

Run
^^^^^^
You then need to run the following commands (in seperate consoles). Run them all from the project root (where manage.py is)

- redis server [This starts the redis message broker].

- celery -A config worker -l info [This starts the celery worker process which will consume the jobs]

- celery -A config beat -l info [This starts the scheduler which will create tasks decorated with @periodic_task.]

- celery flower -A config [OPTIONAL. This runs the celery task viewer.]


