Operating the website
=====================


.. _update_server_code:

Updating the server code
------------------------
- *Production, when there are code updates to apply*
- *Staging, when there are code updates to apply; skip the maintenance message steps*
- *Development servers, when there are code updates to apply; skip the maintenance message and gunicorn steps*

Steps:

#. Put up the maintenance message: ``python manage.py maintenanceon``. Ensure the start time gives users some advance warning.
#. Wait until your specified maintenance time begins.
#. :ref:`Set up your Python/Django environment <script_environment_setup>`.
#. :ref:`Stop gunicorn and other services <script_server_stop>`.

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
#. :ref:`Start gunicorn and other services <script_server_start>`.
#. Check a couple of pages to confirm that things are working.
#. Take down the maintenance message: ``python manage.py maintenanceoff``


Troubleshooting
---------------


Log file locations
..................

- *Django internal server errors*: See `<https://coralnet.ucsd.edu/admin/errorlogs/errorlog/>`__; you must sign in as a site admin.

- *Vision backend*: See ``/srv/www/log``.

- *nginx*: See ``/var/log/nginx``.
