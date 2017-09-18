.. _scripts:

Environment and server scripts
==============================

Most of the setup steps only need to be done once, but there are a few commands that you need to run each time you work on CoralNet. There are also server commands that can be hard to remember. We can put these commands in convenient shell/batch scripts to make life easier.


.. _script_environment_setup:

Environment setup - Linux production/staging servers
----------------------------------------------------
The assumption is that this kind of server does not get restarted regularly, hence the lack of PostgreSQL or Redis commands. You can put this in a ``.sh`` file, and run it with ``source <name>.sh`` whenever you SSH into the server and want to run ``manage.py`` commands:

::

  cd <path up to Git repo>/coralnet/project
  export DJANGO_SETTINGS_MODULE="config.settings.<module name>"
  source <path to virtualenv>/bin/activate


.. _script_server_start:

Server start - Linux production/staging servers
-----------------------------------------------

::

  # Remove the nginx-served maintenance message if it exists.
  rm -f /srv/www/tmp/maintenance.html

  # Set up the Python/Django environment.
  source /scripts/env_setup.sh


  # Start redis, but only if it's not already running.
  # http://stackoverflow.com/a/9118509/
  ps cax | grep redis-server > /dev/null
  if [ $? -eq 0 ]; then
    echo "redis-server is already running."
  else
    echo "Starting redis-server."
    redis server &
  fi

  # Starting webserver and workers
  cd /cnhome
  supervisorctl -c config/supervisor.conf start gunicorn 
  supervisorctl -c config/supervisor.conf start celeryworker
  supervisorctl -c config/supervisor.conf start celerybeat



.. _script_server_stop:

Server stop - Linux production/staging servers
----------------------------------------------

::

  # Stop all gunicorn and celery processes.
  # The purpose here is to allow the Django code to be updated.
  # Redis doesn't need to be stopped because it doesn't run the Django code.
  cd /cnhome
  supervisorctl -c config/supervisor.conf stop gunicorn
  supervisorctl -c config/supervisor.conf stop celeryworker
  supervisorctl -c config/supervisor.conf stop celerybeat

  # Create an HTML file with a maintenance message.
  # Our nginx config should detect a maintenance HTML at this location,
  # and serve it if it exists.
  echo "CoralNet is under maintenance. We'll be back as soon as we can!" > \
    /srv/www/tmp/maintenance.html


Environment setup and services start - Windows development servers
------------------------------------------------------------------
Run this as a ``.bat`` file:

::

  cd D:\<path up to Git repo>\coralnet\project
  set "DJANGO_SETTINGS_MODULE=config.settings.<module name>"

  rem Start the PostgreSQL service (this does nothing if it's already started)
  net start postgresql-x64-<version number>

  rem Start celery.
  rem /B runs a command asynchronously and without an extra command window,
  rem similarly to & in Linux.
  <path to virtualenv>\Scripts\activate.bat
  start /B celery -A config worker

  rem Start celery beat. Could consider commenting this out if you don't
  rem need to submit spacer jobs.
  start /B celery -A config beat

  rem Open a new command window with the virtualenv activated.
  rem Call opens a new command window, cmd /k ensures it waits for input
  rem instead of closing immediately.
  start cmd /k call <path to virtualenv>\Scripts\activate.bat

  rem Run the redis server in this window
  <path to redis>\redis-server.exe

When you're done working:

- Close the command windows
- If you ran celery beat, delete the ``celerybeat.pid`` file from the ``project`` directory (otherwise, a subsequent start of celerybeat will see that file, assume a celerybeat process is still running, and fail to start)


Environment setup -- Mac
------------------------------------

start postgres
::
  postgres -D /usr/local/var/postgres/
set environment variable
::
  export DJANGO_SETTINGS_MODULE=config.settings.dev_beijbom
make sure messaging agent is running
::
  redis-server
start worker
::
  celery -A config worker
(optionally) also start beat which runs scheduled tasks
::
  celery -A config beat
(optionally) also run the celery task viewer:
::
  celery flower -A config

Staging sync - Database
-----------------------

Base this off of: :ref:`database_porting`


Staging sync - S3
-----------------

Base this off of: :ref:`sync_between_s3_buckets`