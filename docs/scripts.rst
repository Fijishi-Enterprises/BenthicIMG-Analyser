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

This sets up the environment (by calling the script above) and then runs gunicorn.

::

  source <environment setup script>.sh
  gunicorn config.wsgi:application --config=config.gunicorn &


.. _script_server_stop:

Server stop - Linux production/staging servers
----------------------------------------------

This kills all running gunicorn processes (one master and one or more workers).

(TODO: Add a "the site is down for maintenance" HTML that's served by nginx when gunicorn is down.)

::

  pkill gunicorn


Staging sync - Database
-----------------------

Base this off of: :ref:`database_porting`


Staging sync - S3
-----------------

Base this off of: :ref:`sync_between_s3_buckets`