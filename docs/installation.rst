Installation
============


Git
-----
Download and install Git, if you don't have it already.

Register an account on `Github <https://github.com/>`__ and ensure you have access to the coralnet repository.

Create an SSH key on your machine for your user profile, and add the public part of the key on your GitHub settings. See `instructions <https://help.github.com/articles/generating-a-new-ssh-key-and-adding-it-to-the-ssh-agent/>`__ on GitHub.

- This process could be optional for a local development machine, but it'll probably be required on the production server. If ``git`` commands result in a ``Permission Denied (publickey)`` error, then you know you have to complete this process. (`Source <https://gist.github.com/adamjohnson/5682757>`__)

- The ``-C`` option on the SSH key creation step doesn't have to be an email address. It's just a comment for you to remember what and who the SSH key is for. (`Source <http://serverfault.com/questions/309171/possible-to-change-email-address-in-keypair>`__)

Git-clone the coralnet repository to your machine.


.. _installation-postgresql:

PostgreSQL
----------
Download and install the PostgreSQL server/core, 9.5.1. 32 or 64 bit shouldn't matter. Make sure you keep track of the root password.

Open pgAdmin. Connect to the server.

Create a user called ``django``.

- In pgAdmin: Right-click Login Roles, New Login Role..., Role name = ``django``, go to Definition tab and add password.

Create a database called ``coralnet``. Owner = ``django``, Encoding = UTF8 (`Django says so <https://docs.djangoproject.com/en/dev/ref/databases/#optimizing-postgresql-s-configuration>`__). Defaults for other options should be fine.

Make sure ``django`` has permission to create databases. This is for running unit tests.

- In pgAdmin: Right click ``django`` login role, Properties..., Role privileges tab, check "Can create databases".

Optimization recommended by Django: set some default parameters for database connections. `See the docs page <https://docs.djangoproject.com/en/dev/ref/databases/#optimizing-postgresql-s-configuration>`__. Can either set these for the ``django`` user with ``ALTER_ROLE``, or for all database users in ``postgresql.conf``.

- ``ALTER_ROLE`` method in pgAdmin: Right click the ``django`` Login Role, Properties, Variables tab. Database = ``coralnet``, Variable Name and Variable Value = whatever is specified in that Django docs link. Click Add/Change to add each of the 3 variables. Click OK.

Two more notes:

- When you create the ``coralnet`` database, it'll have ``public`` privileges by default. This means that every user created in that PostgreSQL installation has certain privileges by default, such as connecting to that database. `Related SO thread <http://stackoverflow.com/questions/6884020/why-new-user-in-postgresql-can-connect-to-all-databases>`__. This shouldn't be an issue as long as we don't have any PostgreSQL users with insecure passwords.

- A Django 1.7 release note says: "When running tests on PostgreSQL, the USER will need read access to the built-in postgres database." This doesn't seem to be a problem by default, probably due to the default ``public`` privileges described above.


Python
------
Download and install Python 2.7.11. 32 bit or 64 bit doesn't matter. It's perfectly fine to keep other Python versions on the same system. Just make sure that your ``python`` and ``pip`` commands point to the correct Python version.

- On Linux, you'll probably have to install this Python version from source.

  - See `Python's docs <https://docs.python.org/2/using/unix.html>`__ for help; download the ``.tgz`` for the desired version, then ``tar xzf Python-<version>.tgz``, then follow the build instructions from there.

  - You probably don't want to change the default Python on your Linux system. To be on the safe side, heed the docs' warning and use ``make altinstall`` instead of ``make install`` to ensure that this Python version gets installed alongside the existing one, without masking/overwriting it.

    - On Ubuntu 14.04, 2015/05/17, the result of ``make altinstall`` is that the original Python 2.7.6 is still at ``/usr/bin/python2.7``, while the newly installed Python 2.7.11 is at ``/usr/local/bin/python2.7``.
    
  - If you get ``configure: error: no acceptable C compiler found in $PATH``, check to see if you have gcc installed: ``sudo apt-cache policy gcc``. If not, then run ``sudo apt-get install gcc``. Then try again.
  
  - If you get ``The program 'make' is currently not installed.``, then do ``sudo apt-get install make``.

Check your pip's version with ``pip -V``. (The pip executable is in the same directory as the python one; make sure you refer to the python/pip you just installed). If pip says it's out of date, it'll suggest that you run a command to update it. Do that.


Virtualenv
----------
Install virtualenv: ``pip install virtualenv`` (Again, be careful about which pip you're using.)

``cd`` to somewhere outside of the ``coralnet`` Git repo. For example, you could go one directory up from the repo.

Create a virtual environment, making sure it uses your preferred Python version: ``virtualenv -p <path to python> <name of new virtualenv directory>`` (Again, find the ``virtualenv`` executable in the same directory as your python/pip executables.)

Activate your virtualenv: ``source <path to virtualenv you created>/bin/activate`` on Linux, ``<path to virtualenv you created>/Scripts/activate`` on Windows.

You should ensure that your virtual environment is activated when installing Python packages or running Django management commands for the CoralNet project. From here on out, these instructions will assume you have your virtual environment (also referred to as virtualenv) activated.


Python packages
---------------
Look under ``requirements`` in the coralnet repository.

- If you are setting up a development machine, you want to use ``requirements/local.txt``.

- If you are setting up the production machine, you want to use ``requirements/production.txt``.

With your virtualenv activated, run ``pip install -r requirements/<name>.txt``.

- When installing ``psycopg2``, if you're on Linux and you get ``Error: pg_config executable not found``, you may have to install a Linux package first: ``postgresql95-devel`` on Red Hat/CentOS, ``libpq-dev`` on Debian/Ubuntu, ``libpq-devel`` on Cygwin/Babun. (`Source <http://stackoverflow.com/questions/11618898/pg-config-executable-not-found>`__)

  - The package may not be in your package directory by default. See PostgreSQL's `Downloads <http://www.postgresql.org/download/>`__ page and follow instructions to get binary packages for your Linux distro.
  
- When installing ``Pillow``, if you're on Linux, you'll get errors if you don't have certain packages:

  - ``ValueError: jpeg is required unless explicitly disabled using --disable-jpeg, aborting``: You need to install libjpeg (jpeg development support). For supported versions of libjpeg, see the `Pillow docs <https://pillow.readthedocs.io/en/latest/installation.html>`__. For example, to use libjpeg version 8 in Ubuntu, install ``libjpeg8-dev``.

  - ``fatal error: Python.h: No such file or directory``: You need to install Python compile headers. In Ubuntu, this is ``python-dev``.

  - PNG related errors are also possible. In Ubuntu, this is ``zlib1g-dev``.

  - There are also other packages that support optional functionality in Pillow. See the `Pillow docs <https://pillow.readthedocs.io/en/latest/installation.html>`__.


Django settings module
----------------------
Look under ``project/config/settings``.

- If you are setting up a development machine, use ``local.py`` at first. If you want to customize some settings for your environment specifically, you can later make another settings file based off of ``local.py``. See ``dev_stephen.py`` for an example.

- If you are setting up the production machine, you want to use ``production.py``.

Django normally expects the settings to be in a ``settings.py`` at the project root, so we have to tell it otherwise. One way is with the ``DJANGO_SETTINGS_MODULE`` environment variable. Set this variable to ``config.settings.<module name>``, where ``<module name>`` is ``local``, ``dev_<name>``, etc.

One way to put all of our Python setup together nicely is with a shell/batch script. On Windows, here's an example batch script that you could run to get a command window for running ``manage.py`` commands:

::

  cd D:\<path up to Git repo>\coralnet\project
  set "DJANGO_SETTINGS_MODULE=config.settings.<module name>"
  cmd /k D:\<path to virtualenv>\Scripts\activate.bat
  
And a shell script for Linux:

::

  cd /srv/www/coralnet/project
  export DJANGO_SETTINGS_MODULE="config.settings.<module name>"
  source /srv/www/<path to virtualenv>/bin/activate


secrets.json
------------
Some settings like passwords shouldn't be committed to the repo. We keep these settings in an un-committed ``project/config/settings/secrets.json`` file. Create this file and fill it with anything that the settings module obtains with ``get_secret()``. For example::

  {
    "DATABASES_PASSWORD": "correcthorsebatterystaple",
    "DATABASES_HOST": "",
    "DATABASES_PORT": ""
  }

If you're missing any secret settings in ``secrets.json``, you'll get an ``ImproperlyConfigured`` error when running any ``manage.py`` commands.

Check your settings module (and anything it imports from, such as ``base.py``) for details on how to specify the required secret settings.


maintenance_notice.html
-----------------------
Look in ``project/templates``. Copy ``maintenance_notice_example.html`` to ``maintenance_notice.html``. This is all you need to do for now. See the docs on putting the site under maintenance (TODO) for more details on what this file is for.


Make some directories
---------------------
Certain file-creation parts of the project code may trigger an error such as ``No such file or directory`` when the destination directory doesn't already exist. This behavior should probably be fixed at some point, but in the meantime, you'll need to create at least the following directories:

- ``<PROCESSING_ROOT>/images/features``
- ``<PROCESSING_ROOT>/images/preprocess``
- ``<PROCESSING_ROOT>/logs``
- ``<PROCESSING_ROOT>/unittests/images/features``
- ``<PROCESSING_ROOT>/unittests/images/preprocess``
- ``<PROCESSING_ROOT>/unittests/logs``
- ``<SHELVED_ANNOTATIONS_DIR>``
- ``<MEDIA_ROOT>/unittests`` (Windows only)


Try running the unit tests
--------------------------
At this point, you should be ready to run the unit test suite to check if everything is working so far.

Run ``python manage.py test``. There may be a few test failures ("F"), but there definitely shouldn't be errors ("E").

If you want to run a subset of the tests, you can use ``python manage.py test <app_name>``, or ``python manage.py test <app_name>.<module>.<TestClass>``.


.. _installation-django-migrations:

Django migrations
-----------------
Run ``python manage.py migrate``. If Django's auth system asks you to create a superuser, then do that.

For information on how to manage migrations from now on, read `Django's docs <https://docs.djangoproject.com/en/dev/topics/migrations/>`__.

If you now run ``manage.py makemigrations`` for all apps, it may create a new migration under the third-party app userena (as of userena 2.0.1 and Django 1.9.5). Making our own migrations for 3rd party apps will almost certainly be problematic when those apps update. So we should delete (and definitely shouldn't run) any userena migrations we make from our runs of makemigrations.

- The main cause of the issue is that Django's EmailField's default max_length changed from 75 to 254 in Django 1.8. userena officially supports Django 1.5 to 1.9, so the reason they haven't added such a migration is probably to be consistent with the earlier versions in that range.

- Here's a `related thread <https://groups.google.com/forum/#!topic/django-developers/rzK7JU-lE8Y>`__ on Google Groups, where a Django core developer says the following: "The recommended way [for third party app maintainers] is to run makemigrations with the lowest version of Django you wish to support. As this recommendation hasn't been tested, let us know if you encounter any problems with it. A potential problem that comes to mind is if you have an EmailField which had its default max_length increased to 254 characters in 1.8."


Try running the server (dev only)
---------------------------------
Run ``python manage.py runserver``. Navigate to your localhost web server, e.g. ``http://127.0.0.1:8000/``, in your browser.

If you created a superuser, log in as that superuser. Try creating a source, uploading images, making annotations, and generally checking various pages. Try checking out the admin interface at ``http://127.0.0.1:8000/admin/``.


Sphinx docs (dev only)
----------------------
Not exactly an installation step, but here's how to build the docs for offline viewing. This can be especially useful when editing the docs.

Go into the ``docs`` directory and run: ``make html``. (This command is cross platform, since there's a ``Makefile`` as well as a ``make.bat``.)

Then you can browse the documentation starting at ``docs/_build/html/index.html``.

It's also possible to output in formats other than HTML, if you use ``make <format>`` with a different format.


PyCharm (dev only)
------------------
Here are some configuration tips for the PyCharm IDE. These instructions refer to PyCharm 2.6.3 (2012/02/26), so some points may be out of date.

How to make PyCharm find everything:

- Make ``coralnet`` your PyCharm project root.

- Go to the Django Support settings and use ``project`` as the Django project root. Also set your Manage script (``manage.py``) and Settings file accordingly.

- Go to the Project Interpreter settings and select the Python within your virtualenv (should be under ``Scripts``). This should make PyCharm detect our third-party Python apps.

- Go to the Project Structure settings and mark ``project`` as a Sources directory (`Help <https://www.jetbrains.com/help/pycharm/2016.1/configuring-folders-within-a-content-root.html>`__). This is one way to make PyCharm recognize imports of our apps, such as ``annotations.models``. (There may be other ways.)

- Go to the Python Template Languages settings. Under Template directories, add one entry for each ``templates`` subdirectory in the repository.

How to make a Run Configuration that runs ``manage.py runserver`` from PyCharm:

- Run -> Edit Configurations..., then make a new configuration under "Django server".

- Add an environment variable with Name ``DJANGO_SETTINGS_MODULE`` and Value ``config.settings.<name>``, with <name> being ``local``, ``dev_stephen``, etc. [#pycharmenvvar]_

- Ensure that "Python interpreter" has the Python from your virtualenv.

.. [#pycharmenvvar] Not sure why this is needed when we specify the settings module in Django Support settings, but it was needed in my experience. -Stephen

