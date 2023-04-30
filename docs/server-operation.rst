Server operation
================


Updating to the latest repository code
--------------------------------------
#. Get the new code from Git.

   - To update the master branch, ``git checkout master`` and ``git pull origin master``.

   - If you have a feature branch that you want updated, checkout that branch, then ``git rebase master``.

#. Follow the instructions in coralnet's ``CHANGELOG.md`` to update from the old version to the latest version.

   - Python packages can be installed/upgraded with ``pip install -U -r ../requirements/<name>.txt``. If it subsequently advises you to upgrade pip, then do so.

   - Run Django migrations with ``python manage.py migrate``.

   - If part of the update requires intermediate steps, the version tags can help. For example, do ``git pull origin 1.4``, take any steps required between 1.4 and 1.5, then do another git-pull and repeat as needed.


Upgrading Python
----------------
If you are just upgrading the patch version (3.10.0 -> 3.10.1), you should be able to just download and install the new version, allowing it to overwrite your old version. (`Source <https://stackoverflow.com/a/17954487/>`__)

- If using Windows, you should also create a new virtual environment using the new version, because venv on Windows might only copy core files/scripts over instead of using symlinks.

If you are upgrading the major version (2 -> 3) or minor version (3.9 -> 3.10), first download and install the new version. It should install in a separate location, such as ``python37`` instead of ``python36``. You'll then want to :ref:`create a new virtual environment <virtual_environment>` using the new Python version, and :ref:`reinstall packages <python-packages>` to that new virtual environment.

The Django file-based cache uses a different pickle protocol in Python 2 versus 3, so you'll have to clear the Django cache when switching between Python 2 and 3, otherwise you may see errors on the website.


Upgrading PostgreSQL
--------------------
See the `PostgreSQL docs <https://www.postgresql.org/docs/14/upgrading.html>`__. Basically:

- Install the new PostgreSQL server version alongside the existing version.

  - Note that if both server versions use the same port number (e.g. 5432, the default), they won't be able to run simultaneously.

- Check the release notes for the major version (9.5, 9.6, 10, 11, 12...), particularly the 'Migration' section, to see if version-specific steps are necessary to upgrade.

  - `Upgrading to version 10: <https://www.postgresql.org/docs/10/release-10.html>`__ No extra steps needed for CoralNet. If you happen to connect to your development server remotely, though, ``ssl_dh_params_file`` could be helpful for security.

- Either manually dump your databases from the old server (``dumpall``) and restore them to the new server (``psql`` with ``--file`` option), or use ``pg_upgrade`` to do it.

  - If you get prompted for the password several times during the process, just enter the password each time and it should work.


Server scripts
--------------

There are a few commands that you generally need to run each time you work on CoralNet. You can put these commands in convenient shell/batch scripts to make life easier.

Note that huey won't start up successfully if in immediate mode (the default for development), but it's no harm to just let it attempt to start up and get an error.


Environment setup and services start - Windows
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Run this as a ``.bat`` file:

.. code-block:: doscon

  cd <path up to Git repo>\coralnet\project
  set "DJANGO_SETTINGS_MODULE=config.settings.<module name>"

  rem Add ffmpeg DLL to PATH. torchvision 0.5.0 appears to need this.
  rem https://github.com/pytorch/vision/issues/1877
  set "PATH=%PATH%;<path up to ffmpeg>\ffmpeg-4.1-win64-shared\bin"

  rem Start the PostgreSQL service (this does nothing if it's already started)
  net start postgresql-x64-<version number>

  rem Start huey.
  rem call runs another batch file and then returns control to this batch file.
  rem start /B runs a command asynchronously and without an extra command window,
  rem similarly to & in Linux.
  call <path to virtual environment>\Scripts\activate.bat
  start /B python manage.py run_huey

  rem Open a new command window with the virtual environment activated.
  rem Call opens a new command window, cmd /k ensures it waits for input
  rem instead of closing immediately.
  start cmd /k call <path to virtual environment>\Scripts\activate.bat

  rem Run the redis server in this window
  <path to redis>\redis-server.exe

When you're done working, close the command windows.


Environment setup -- Mac
^^^^^^^^^^^^^^^^^^^^^^^^

start postgres::

  postgres -D /usr/local/var/postgres/

set environment variable::

  export DJANGO_SETTINGS_MODULE=config.settings.dev_beijbom

make sure messaging agent is running::

  redis-server

start huey::

  python manage.py run_huey


Checking test coverage
----------------------
We have the ``coverage`` Python package in our local requirements for this purpose. Follow the instructions in `the coverage docs <https://coverage.readthedocs.io/en/stable/>`__ to run it and view the results.

- To run our Django tests with coverage, run ``coverage run manage.py test`` from the ``project`` directory.


Admin-only website functionality
--------------------------------

Writing blog posts
^^^^^^^^^^^^^^^^^^

Blog posts are only writable and editable through the admin section of the site. Head to the admin section (Admin Tools at top bar, then Admin Site), then under "BLOG", select "Blog posts". This should show a list of existing blog posts.

At the blog posts listing, click "ADD BLOG POST +" at the top right to start writing a new blog post. The fields should be explained by the help text on the page. In "Content", you can include images using drag and drop.

You need to Save your post in order to preview it. Make sure you leave "Is published" unchecked to save your post as a private draft (only viewable by site admins). Then go to the main site's Blog section, find your draft, and look over it. If you think it's ready to publish, check "Is published" and Save again.

We'll use Google Groups for blog comments, so we don't have to maintain a separate blog comments system. This also doubles as a simple way to announce blog posts (for those subscribed to the Google Group). After publishing a blog post, you'll want to create a Google Groups thread for discussion of the new post, which links to that post. Then you'll also want to edit the blog post to link to that Google Groups thread, like: ``Discuss this article here: <link>``. Later, we might come up with a way to automatically create the Google Groups thread (using a CoralNet email address), but for now it has to be done manually.
