Server operation
================


Updating to the latest repository code
--------------------------------------
#. Get the new code from Git.

   - To update the master branch, ``git pull origin master``.

     - Or, if you want to review changes before updating: ``git fetch origin``, ``git checkout master``, and ``git rebase origin/master``.

#. Check if there are any changes to requirements files. If there are any new Python packages or package updates to install, then install them: ``pip install -U -r ../requirements/<name>.txt``.

   - If it subsequently advises you to update pip, then do so.

#. Check changes to settings files. If there are any new secret settings to specify in ``secrets.json``, then do that.

#. If there are any new Django migrations to run, then run those: ``python manage.py migrate``.


Upgrading Python
----------------
If you are just upgrading the patch version (3.6.12 -> 3.6.13), you should be able to just download and install the new version, allowing it to overwrite your old version. (`Source <https://stackoverflow.com/a/17954487/>`__)

- If using Windows, you should also create a new virtualenv using the new version, because virtualenv on Windows copies core files/scripts over instead of using symlinks.

If you are upgrading the major version (2 -> 3) or minor version (3.6 -> 3.7), first download and install the new version. It should install in a separate location, such as ``python37`` instead of ``python36``. You'll then want to :ref:`create a new virtualenv <virtualenv>` using the new Python version, and :ref:`reinstall packages <python-packages>` to that new virtualenv.

The Django file-based cache uses a different pickle protocol in Python 2 versus 3, so you'll have to clear the Django cache when switching between Python 2 and 3, otherwise you may see errors on the website.


Upgrading PostgreSQL
--------------------
See the `PostgreSQL docs <https://www.postgresql.org/docs/10/upgrading.html>`__. Basically:

- Install the new PostgreSQL server version alongside the existing version.

  - Note that if both server versions use the same port number (e.g. 5432, the default), they won't be able to run simultaneously.

- Check the release notes for the major version (9.5, 9.6, 10, 11, 12...), particularly the 'Migration' section, to see if version-specific steps are necessary to upgrade.

  - `Upgrading to version 10: <https://www.postgresql.org/docs/10/release-10.html>`__ No extra steps needed for CoralNet. If you happen to connect to your development server remotely, though, ``ssl_dh_params_file`` could be helpful for security.

- Either manually dump your databases from the old server (``dumpall``) and restore them to the new server (``psql`` with ``--file`` option), or use ``pg_upgrade`` to do it.

  - If you get prompted for the password several times during the process, just enter the password each time and it should work.


Server scripts
--------------

There are a few commands that you generally need to run each time you work on CoralNet. You can put these commands in convenient shell/batch scripts to make life easier.


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

  rem Start celery.
  rem /B runs a command asynchronously and without an extra command window,
  rem similarly to & in Linux.
  <path to virtualenv>\Scripts\activate.bat
  start /B celery -A config worker

  rem If this file exists, it could interfere with celerybeat starting up.
  del <path up to Git repo>\coralnet\project\celerybeat.pid

  rem Start celery beat. Could consider commenting this out if you don't
  rem need to submit spacer jobs.
  start /B celery -A config beat

  rem Open a new command window with the virtualenv activated.
  rem Call opens a new command window, cmd /k ensures it waits for input
  rem instead of closing immediately.
  start cmd /k call <path to virtualenv>\Scripts\activate.bat

  rem Run the redis server in this window
  <path to redis>\redis-server.exe

When you're done working, close the command windows.


Environment setup -- Mac
^^^^^^^^^^^^^^^^^^^^^^^^

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


Checking test coverage
----------------------
We have the ``coverage`` Python package in our local requirements for this purpose. Follow the instructions in `the coverage docs <https://coverage.readthedocs.io/en/stable/>`__ to run it and view the results.

- To run our Django tests with coverage, run ``coverage run manage.py test`` from the ``project`` directory.


Admin-only website functionality
--------------------------------

Writing blog posts
^^^^^^^^^^^^^^^^^^

Blog entries (AKA articles, posts) are only writable and editable through the admin section of the site. Head to the admin section (``<site domain>/admin``), then under "Andablog", select "Entries". This should show a list of existing blog entries.

At the Andablog Entries listing, click "Add Entry +" at the top right to start writing a new blog entry:

- Title is the entry's title.
- Content is the entry's body text.
- You can select a "Content markup type", but Markdown is recommended to be consistent.

You need to Save your entry in order to preview it. Make sure you leave "Is published" unchecked to save your entry as a private draft (only viewable by site admins). Then go to the main site's Blog section, find your draft, and look over it. If you think it's ready to publish, check "Is published" and Save again.

To add an image to a blog entry, first scroll to the Entry Images section at the bottom, and select an image to upload. Click "Save and continue editing" to save the image (this also saves the blog entry). Once saved, the image's URL will be shown in the Entry Images section. Use this image URL to embed the image in your article - here's a Markdown example: ``![Alt text goes here](/media/andablog/images/my_image.png)``

We'll use Google Groups for blog comments, so we don't have to maintain a separate blog comments system. This also doubles as a simple way to announce blog posts (for those subscribed to the Google Group). After publishing a blog entry, you'll want to create a Google Groups thread for discussion of the new entry, which links to that entry. Then you'll also want to edit the blog entry to link to that Google Groups thread, like: ``Discuss this article here: <link>``. Later, we might come up with a way to automatically create the Google Groups thread (using a CoralNet email address), but for now it has to be done manually.

Optional fields when editing blog entries:

- Tags aren't used yet, but we might use them later when we have more articles and want to make them searchable. It's up to you if you want to add tags for now.
- Preview Content allows you to customize the text that appears for this article in the Blog section's entry listing. Normally the listing just shows the first X words of the article, but if Preview Content is specified for the article, then Preview Content is used instead. You can further customize the entry-listing preview with Preview Image.

Other notes about the entry-editing interface:

- The Save buttons and the Delete button (when editing an existing entry) at the bottom apply to the whole blog entry, not just the images. Don't be misled by the fact that they're right under the Entry Images section.
- When editing an existing entry, the "View on Site >" button at the top right doesn't work for now. Perhaps we'll fix it later.
