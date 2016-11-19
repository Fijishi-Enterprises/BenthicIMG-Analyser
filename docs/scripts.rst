.. _scripts:

Environment and server scripts
==============================

Most of the setup steps only need to be done once, but there are a few commands that you need to run each time you work on CoralNet. There are also server commands that can be hard to remember. We can put these commands in convenient shell/batch scripts to make life easier.


Environment setup - Windows development servers
-----------------------------------------------
Starts the PostgreSQL service, starts the Redis server, and opens a command window for running ``manage.py`` commands. Run this as a ``.bat`` file:

::

  cd D:\<path up to Git repo>\coralnet\project
  set "DJANGO_SETTINGS_MODULE=config.settings.<module name>"

  rem Start the PostgreSQL service (this does nothing if it's already started)
  net start postgresql-x64-<version number>

  rem Call opens a new command window, cmd /k ensures it waits for input
  rem instead of closing immediately
  start cmd /k call <path to virtualenv>\Scripts\activate.bat

  rem Run the redis server in this window
  <path to redis>\redis-server.exe


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
  source <environment setup script>.sh

  echo "(Re)starting gunicorn."
  pkill gunicorn
  gunicorn config.wsgi:application --config=config/gunicorn.py &

  # Start redis, but only if it's not already running.
  # http://stackoverflow.com/a/9118509/
  ps cax | grep redis-server > /dev/null
  if [ $? -eq 0 ]; then
    echo "redis-server is already running."
  else
    echo "Starting redis-server."
    redis server &
  fi

  # (Re)start celery processes.
  # It's probably possible to check what's already running, and only start
  # stuff as needed. If you know how, implement that here.
  echo "(Re)starting celery processes."
  pkill celery
  # Worker(s).
  celery worker --app=config --loglevel=info &
  # Scheduler which creates tasks.
  celery beat --app=config --loglevel=info &
  # Task viewer.
  celery flower --app=config &


.. _script_server_stop:

Server stop - Linux production/staging servers
----------------------------------------------

::

  # Stop all gunicorn processes.
  # The purpose here is just to allow the Django code to be updated,
  # so redis and celery don't need to be stopped.
  echo "Stopping gunicorn."
  pkill gunicorn

  # Create an HTML file with a maintenance message.
  # Our nginx config should detect a maintenance HTML at this location,
  # and serve it if it exists.
  echo "CoralNet is under maintenance. We'll be back as soon as we can!" > \
    /srv/www/tmp/maintenance.html


Staging sync - Database
-----------------------

Base this off of: :ref:`database_porting`


Staging sync - S3
-----------------

Base this off of: :ref:`sync_between_s3_buckets`