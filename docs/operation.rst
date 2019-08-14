Operating the website
=====================


.. _update_server_code:

Updating the server code
------------------------
- *Production, when there are code updates to apply*
- *Staging, when there are code updates to apply; skip the maintenance message steps*
- *Development servers, when there are code updates to apply; skip the maintenance message and gunicorn steps*

Steps:

#. :ref:`Set up your Python/Django environment <script_environment_setup>`.
#. Put up the maintenance message: ``python manage.py maintenanceon``. Ensure the start time gives users some advance warning.
#. Wait until your specified maintenance time begins.
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


.. _writing_blog_posts:

Writing blog posts
------------------

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



Troubleshooting
---------------


Log file locations
..................

- *Django internal server errors*: See `<https://coralnet.ucsd.edu/admin/errorlogs/errorlog/>`__; you must sign in as a site admin.

- *Vision backend*: See ``/srv/www/log``.

- *nginx*: See ``/var/log/nginx``.
