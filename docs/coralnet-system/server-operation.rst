Operating and maintaining production/staging servers
====================================================


Updating the server code
------------------------

#. :ref:`Set up your Python/Django environment <script-environment-setup>`.
#. Put up the maintenance message: ``python manage.py maintenanceon``. Ensure the start time gives users some advance warning.
#. Wait until your specified maintenance time begins.
#. :ref:`Stop gunicorn and other services <script-server-stop>`.

   - When we're using gunicorn instead of the Django ``runserver`` command, updating code while the server is running can temporarily leave the server code in an inconsistent state, which can lead to some very weird internal server errors.
   - When using the Django ``runserver`` command, there are still situations where you need to stop and re-start the server, such as when adding new files. `Link <https://docs.djangoproject.com/en/dev/ref/django-admin/#runserver>`__

#. Get the new code from Git.

   - If you're sure you don't have any code changes on your end (e.g. most of the time for the production server), you should just need ``git fetch origin``, ``git checkout master``, and ``git rebase origin/master``.

#. If there are any new Python packages or package upgrades to install, then install them: ``pip install -U -r ../requirements/<name>.txt``.

   - If it subsequently advises you to upgrade pip, then do so.

#. If there are any new secret settings to specify in ``secrets.json``, then do that.
#. If any static files (CSS, Javascript, etc.) were added or changed, run ``python manage.py collectstatic`` to serve those new static files.

   - Do ``python manage.py collectstatic --clear`` if you think there's some obsolete static files that can be cleaned up.

#. If there are any new Django migrations to run, then run those: ``python manage.py migrate``. New migrations should be tested in staging before being run in production.
#. :ref:`Start gunicorn and other services <script-server-start>`.
#. Check a couple of pages to confirm that things are working.
#. Take down the maintenance message: ``python manage.py maintenanceoff``


.. _server-scripts:

Shell scripts for operating the server
--------------------------------------


.. _script-environment-setup:

Environment setup
^^^^^^^^^^^^^^^^^
The assumption is that this kind of server does not get restarted regularly, hence the lack of PostgreSQL or Redis commands. You can put this in a ``.sh`` file, and run it with ``source <name>.sh`` whenever you SSH into the server and want to run ``manage.py`` commands:

::

  cd <path up to Git repo>/coralnet/project
  export DJANGO_SETTINGS_MODULE="config.settings.<module name>"
  source <path to virtualenv>/bin/activate


.. _script-server-start:

Server start
^^^^^^^^^^^^

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


.. _script-server-stop:

Server stop
^^^^^^^^^^^

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


Updating software versions
--------------------------


Linux packages
^^^^^^^^^^^^^^
When you log into Ubuntu, it should say how many updates are available. If there are one or more updates, run ``sudo apt-get update`` then ``sudo apt-get upgrade``.


Linux kernel
^^^^^^^^^^^^
When you log into Ubuntu, it might say "System restart required". This is probably because some of the updates are part of the kernel (`Link <http://superuser.com/questions/498174/>`__).

There are non-trivial ways of applying even these updates without restarting. One way is to use Oracle's `ksplice <http://www.ksplice.com/>`__, but this software isn't free for Ubuntu Server.

If a restart is acceptable, here's a simple update procedure:

- Log into the EC2 instance. Put up the maintenance message and wait for the maintenance time.

- Stop gunicorn. ``sudo apt-get update`` then ``sudo apt-get upgrade`` (assuming Ubuntu). Log out. Go to the EC2 dashboard and reboot the EC2 instance. Wait for the reboot to finish.

- Log in again. Start redis, nginx (if not auto-starting), and gunicorn. Take down the maintenance message.


Linux version
^^^^^^^^^^^^^
Probably the most doubt-free way to do this is to create a new EC2 instance with that new Linux version, and migrate the server to that EC2 instance. This can be a relatively quick process if you have a Docker file specifying how to set up a new instance.

However, if you want to try upgrading the Linux version on an instance, it should be possible. In this case it should say "you can run ``do-release-upgrade`` to upgrade".

It'll advise you that the restart of certain services could interrupt your SSH session, and that this can be mitigated by opening access to port 1022. Go ahead and do that in the EC2 instance's security group.


nginx
^^^^^
nginx releases security fixes every so often, but these fixes might not make it to the default apt repository.

According to `this page <http://nginx.org/en/linux_packages.html#stable>`__, you'll want to add the following to the end of the ``/etc/apt/sources.list`` file:

::

  deb http://nginx.org/packages/ubuntu/ codename nginx
  deb-src http://nginx.org/packages/ubuntu/ codename nginx

Where ``codename`` is, for example, ``xenial`` for Ubuntu 16.04.

(TODO: It seems a GPG key needs to be added as well, otherwise apt-get update doesn't work?)

Now whenever you want to update, run:

::

  sudo /etc/init.d/nginx stop
  sudo apt-get update
  sudo apt-get install nginx
  sudo /etc/init.d/nginx start


PostgreSQL
^^^^^^^^^^
When using RDS, minor version upgrades (e.g. 9.6.0 to 9.6.1) should be done automatically if you specified this behavior in the instance creation options.

(TODO: See if upgrading a non-minor version also means ``psycopg2`` should be re-installed with a corresponding upgraded version of ``libpg-dev``.)


Troubleshooting
---------------


Log file locations
^^^^^^^^^^^^^^^^^^

- *Django internal server errors*: See `<https://coralnet.ucsd.edu/admin/errorlogs/errorlog/>`__; you must sign in as a site admin.

- *Vision backend*: See ``/srv/www/log``.

- *nginx*: See ``/var/log/nginx``.


Running the staging server with the runserver command
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Occasionally, it can be convenient to use ``runserver`` on the staging server. For example, perhaps you are debugging an issue that only occurs when there are large volumes of data, and does not require ``DEBUG = False`` to occur. Here's how to do it:

- Ensure the virtualenv is activated, and run ``python manage.py runserver`` from the ``project`` directory.

- Set up an `SSH tunnel <http://www.sotechdesign.com.au/browsing-the-web-through-a-ssh-tunnel-with-firefox-and-putty-windows/>`__ from your local machine to the EC2 instance. Make sure your browser's proxy settings do NOT exclude localhost or 127.0.0.1 from the SSH tunnel. Then navigate to ``http://127.0.0.1:8000/`` in your browser to view the website.


Things to change after a suspected breach
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
High priority:

- AWS/IAM passwords
- Database passwords, especially the password Django uses to authenticate
- EBS volume (create a new one)

Medium priority:

- Website admins' passwords (can also revoke admin status from inactive admins)
- Other website users' passwords (tell them to change their passwords)
- Django secret key
- SSH key from the server machine to GitHub (can be revoked from GitHub's website)

Lower priority:

- Google Maps API key
