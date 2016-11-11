.. _python_and_django:

Python and Django
=================

This page details Python and Django related setup steps.


Python
------
Download and install the latest Python 2.7.x. 32 bit or 64 bit doesn't matter. It's perfectly fine to keep other Python versions on the same system. Just make sure that your ``python`` and ``pip`` commands point to the correct Python version.

- On Linux, you'll probably have to install this Python version from source.

  - See `Python's docs <https://docs.python.org/2/using/unix.html>`__ for help; download the ``.tgz`` for the desired version, then ``tar xzf Python-<version>.tgz``, then follow the build instructions from there.

  - You probably don't want to change the default Python on your Linux system. To be on the safe side, heed the docs' warning and use ``make altinstall`` instead of ``make install`` to ensure that this Python version gets installed alongside the existing one, without masking/overwriting it.

    - On Ubuntu 14.04, 2015/05/17, the result of ``make altinstall`` is that the original Python 2.7.6 is still at ``/usr/bin/python2.7``, while the newly installed Python 2.7.11 is at ``/usr/local/bin/python2.7``.

    - It seems to be a standard practice to put self-installed packages in ``/usr/local`` like this. `Link 1 <http://askubuntu.com/a/34922/>`__, `Link 2 <http://unix.stackexchange.com/a/11552/>`__

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

A few package/OS combinations may need additional steps:

- ``psycopg2`` on Linux

  - If you get ``Error: pg_config executable not found``, you may have to install a Linux package first: ``postgresql<version>-devel`` on Red Hat/CentOS, ``libpq-dev`` on Debian/Ubuntu, ``libpq-devel`` on Cygwin/Babun. (`Source <http://stackoverflow.com/questions/11618898/pg-config-executable-not-found>`__)

  - The package may not be in your package directory by default. See PostgreSQL's `Downloads <http://www.postgresql.org/download/>`__ page and follow instructions to get binary packages for your Linux distro.

- ``Pillow`` on Linux

  - You'll get errors if you don't have certain packages:

    - ``ValueError: jpeg is required unless explicitly disabled using --disable-jpeg, aborting``: You need to install libjpeg (jpeg development support). For supported versions of libjpeg, see the `Pillow docs <https://pillow.readthedocs.io/en/latest/installation.html>`__. For example, to use libjpeg version 8 in Ubuntu, install ``libjpeg8-dev``.

    - ``fatal error: Python.h: No such file or directory``: You need to install Python compile headers. In Ubuntu, this is ``python-dev``.

    - PNG related errors are also possible. In Ubuntu, this is ``zlib1g-dev``.

  - There are also other packages that support optional functionality in Pillow. See the `Pillow docs <https://pillow.readthedocs.io/en/latest/installation.html>`__.

- ``scipy`` on Windows

  - Installing SciPy with the requirements file will fail for two reasons. First, NumPy needs to be installed as NumPy+MKL, and the binary for that isn't on PyPI. Second, even after getting the NumPy install right, installing SciPy with pip fails for some reason (the first problem is ``libraries openblas not found in [ ... ] NOT AVAILABLE``).

  - What to do: First install NumPy+MKL and then SciPy manually using the .whl files here: http://www.lfd.uci.edu/~gohlke/pythonlibs/ Be sure to pick the appropriate .whl depending on whether your Python is 32 or 64 bit. To install a .whl, run ``pip install <path to .whl>``. Then run the requirements file to install the rest of the packages.

- ``Twisted`` on Windows

  - Similarly to SciPy, this should be installed manually using the .whl files at the aforementioned link.


Django settings module
----------------------
Look under ``project/config/settings``.

- If you are setting up a development server, use one of the dev-specific settings modules (such as ``dev_stephen.py``) or make your own. The module should include:

  - An import of ``base_devserver``
  - An import of either ``storage_local`` or ``storage_s3``, depending on whether you want to store media files locally or in an S3 bucket
  - Any settings values you want to customize for your environment specifically

- The production server should use ``production.py``.
- The staging server should use ``staging.py``.

Django normally expects the settings to be in a ``settings.py`` at the project root, so we have to tell it otherwise. One way is with the ``DJANGO_SETTINGS_MODULE`` environment variable. Set this variable to ``config.settings.<module name>``, where ``<module name>`` is ``dev_<name>``, ``production``, etc.


secrets.json
------------
Some settings like passwords shouldn't be committed to the repo. We keep these settings in an un-committed ``project/config/settings/secrets.json`` file. Create this file and fill it with anything that the settings module obtains with ``get_secret()``. For example::

  {
    "DATABASES_PASSWORD": "correcthorsebatterystaple",
    "DATABASES_HOST": "",
    "DATABASES_PORT": ""
  }

If you're missing any secret settings in ``secrets.json``, you'll get an ``ImproperlyConfigured`` error when running any ``manage.py`` commands.

Check your settings module (and anything it imports from, such as ``base.py``) for details on the format of each required secret setting.


maintenance_notice.html
-----------------------
Look in ``project/templates``. Copy ``maintenance_notice_example.html`` to ``maintenance_notice.html``. This is all you need to do for now. See the docs on putting the site under maintenance (TODO) for more details on what this file is for.


Make some directories
---------------------
Certain file-creation parts of the project code may trigger an error such as ``No such file or directory`` when the destination directory doesn't already exist. This behavior should probably be fixed at some point, but in the meantime, you'll need to create at least the following directories:

- ``project/logs``
- ``<MEDIA_ROOT>/unittests`` (Windows only)


Try running the unit tests
--------------------------
At this point, you should be ready to run the unit test suite to check if everything is working so far.

Run ``python manage.py test``. Test failures will be shown as F, and errors will be shown as E.

If you want to run a subset of the tests, you can use ``python manage.py test <app_name>``, or ``python manage.py test <app_name>.<module>.<TestClass>``.


Django migrations
-----------------
Run ``python manage.py migrate``. If Django's auth system asks you to create a superuser, then do that.

For information on how to manage migrations from now on, read `Django's docs <https://docs.djangoproject.com/en/dev/topics/migrations/>`__.


Sphinx docs
-----------
- *Development machine*

Not exactly an installation step, but here's how to build the docs for offline viewing. This can be especially useful when editing the docs.

Go into the ``docs`` directory and run: ``make html``. (This command is cross platform, since there's a ``Makefile`` as well as a ``make.bat``.)

Then you can browse the documentation starting at ``docs/_build/html/index.html``.

It's also possible to output in formats other than HTML, if you use ``make <format>`` with a different format.


PyCharm
-------
- *Development machine*

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


Upgrading Python version
------------------------
TODO