Installation
============


Git
-----
Download and install Git, if you don't have it already.

Register an account on `Github <https://github.com/>`_ and ensure you have access to the coralnet repository.

Git-clone the coralnet repository to your machine.


PostgreSQL
----------
Download and install the PostgreSQL server/core, 9.5.1. 32 or 64 bit shouldn't matter. Make sure you keep track of the root password.

In PostgreSQL, create a database called ``coralnet``. Owner = ``postgres``, Encoding = UTF8 (`Django says so <https://docs.djangoproject.com/en/dev/ref/databases/#optimizing-postgresql-s-configuration>`_). Defaults for other options should be fine.

- On Windows: Open pgAdmin III, connect to the server, then right-click the Databases item and select "New Database...".

Create a user called ``django``. Give ``django`` permission to do anything with ``coralnet``.

- On Windows:

  - New Group Role..., Role name = ``coralnet_admin``, click OK.
  - Right click coralnet database, go to Privileges tab, select 'group coralnet_admin' in the Role dropdown, check ALL, click Add/Change, click OK.
  - New Login Role..., Role name = ``django``, go to Definition tab and add password, go to Role membership tab and add ``coralnet_admin``, click OK.

Also make sure ``django`` has permission to create databases. This is for running unit tests.

- On Windows: Right click ``django`` login role, Properties..., Role privileges tab, check "Can create databases". [#dbcreateperm]_

.. [#dbcreateperm] I initially tried doing this with the ``coralnet_admin`` group role, but ``django`` still wasn't able to create databases. I had to edit the Login Role instead, for some reason. -Stephen

Optimization recommended by Django: set some default parameters for database connections. `See the docs page <https://docs.djangoproject.com/en/dev/ref/databases/#optimizing-postgresql-s-configuration>`_. Can either set these for the ``django`` user with ``ALTER_ROLE``, or for all database users in ``postgresql.conf``.

- ``ALTER_ROLE`` method on Windows: Right click the ``django`` Login Role, Properties, Variables tab. Database = ``coralnet``, Variable Name and Variable Value = whatever is specified in that Django docs link. Click Add/Change to add each of the 3 variables. Click OK.

Two more notes:

- When you create the ``coralnet`` database, it'll have ``public`` privileges by default. This means that every user created in that PostgreSQL installation has certain privileges by default, such as connecting to that database. `Related SO thread <http://stackoverflow.com/questions/6884020/why-new-user-in-postgresql-can-connect-to-all-databases>`_. This shouldn't be an issue as long as we don't have any PostgreSQL users with insecure passwords.

- A Django 1.7 release note says: "When running tests on PostgreSQL, the USER will need read access to the built-in postgres database." This doesn't seem to be a problem by default, probably due to the default ``public`` privileges described above.

For the 2016 production-server database migration process, see: TODO


Python
------
Download and install Python 2.7.11. 32 bit or 64 bit doesn't matter. It's perfectly fine to keep other Python versions on the same system. Just make sure that your ``python`` and ``pip`` commands point to the correct Python version.

Upgrade pip: ``python -m pip install -U pip``


Virtualenv
----------
Install virtualenv: ``pip install virtualenv``

Create a virtual environment as described in the `Virtualenv docs <https://virtualenv.pypa.io/en/latest/userguide.html>`_. Create the virtual environment outside of your cloned Git repo; for example, you could create it one directory up from the repo.

You should ensure that your virtual environment is activated when installing Python packages or running Django management commands for the CoralNet project. From here on out, these instructions will assume you have your virtual environment (also referred to as virtualenv) activated.


Python packages
---------------
Look under ``requirements`` in the coralnet repository.

- If you are setting up a development machine, you want to use ``requirements/local.txt``.

- If you are setting up the production machine, you want to use ``requirements/production.txt``.

With your virtualenv activated, run ``pip install -r requirements/<name>.txt``.


Django settings module
----------------------
Look under ``project/config/settings``.

- If you are setting up a development machine, use ``local.py`` at first. If you want to customize some settings for your environment specifically, you can later make another settings file based off of ``local.py``. See ``dev_stephen.py`` for an example.

- If you are setting up the production machine, you want to use ``production.py``.

Django normally expects the settings to be in a ``settings.py`` at the project root, so we have to tell it otherwise. One way is with the ``DJANGO_SETTINGS_MODULE`` environment variable. Set this variable to ``config.settings.<module name>``, where ``<module name>`` is ``local``, ``dev_<name>``, etc.

One way to put all of our Python setup together nicely is with a shell/batch script. On Windows, here's an example batch script that you could run to get a command window for running ``manage.py`` commands:

::

  cd D:\<path up to Git repo>\coralnet\project
  set "DJANGO_SETTINGS_MODULE=config.settings.dev_<name>"
  cmd /k D:\<path to virtualenv>\Scripts\activate.bat


secrets.json
------------
Some settings like passwords shouldn't be committed to the repo. We keep these settings in an un-committed ``project/config/settings/secrets.json`` file. Create this file and fill it with anything that the settings module obtains with ``get_secret()``. For example::

  {
    "DATABASES_PASSWORD": "correcthorsebatterystaple",
    "DATABASES_HOST": "",
    "DATABASES_PORT": ""
  }

If you're missing any secret settings in ``secrets.json``, you'll get an ``ImproperlyConfigured`` error when running any ``manage.py`` commands.


maintenance_notice.html
-----------------------
Look in ``project/templates``. Copy ``maintenance_notice_example.html`` to ``maintenance_notice.html``. This is all you need to do for now. See the docs on putting the site under maintenance (TODO) for more details on what this file is for.


Try running the unit tests
--------------------------
At this point, you should be ready to run the unit test suite to check if everything is working so far.

Run ``python manage.py test``. There may be a few test failures ("F"), but there definitely shouldn't be errors ("E").

If you want to run a subset of the tests, you can use ``python manage.py test <app_name>``, or ``python manage.py test <app_name>.<module>.<TestClass>``.


Django migrations
-----------------
Run ``python manage.py migrate``. If Django's auth system asks you to create a superuser, then do that.

For information on how to manage migrations from now on, read `Django's docs <https://docs.djangoproject.com/en/dev/topics/migrations/>_`.

For the 2016 production-server Django migration process, see: TODO


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

- Go to the Project Structure settings and mark ``project`` as a Sources directory (`Help <https://www.jetbrains.com/help/pycharm/2016.1/configuring-folders-within-a-content-root.html>`_). This is one way to make PyCharm recognize imports of our apps, such as ``annotations.models``. (There may be other ways.)

How to make a Run Configuration that runs ``manage.py runserver`` from PyCharm:

- Run -> Edit Configurations..., then make a new configuration under "Django server".

- Add an environment variable with Name ``DJANGO_SETTINGS_MODULE`` and Value ``config.settings.<name>``, with <name> being ``local``, ``dev_stephen``, etc. [#pycharmenvvar]_

- Ensure that "Python interpreter" has the Python from your virtualenv.

.. [#pycharmenvvar] Not sure why this is needed when we specify the settings module in Django Support settings, but it was needed in my experience. -Stephen

