Web server design notes
=======================


Web server software choice
--------------------------
We chose nginx, but it was not the only server software we tried:


Tried Apache + mod_wsgi, but didn't get it up and running (2016)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Here is what we included for CoralNet in the ``httpd.conf``:

::

  # Django - Serve static files from local directories.
  # Format: Alias STATIC_URL STATIC_ROOT
  # <Directory STATIC ROOT>

  Alias /static/ /srv/www/static_serve/

  <Directory /srv/www/static_serve>
  Require all granted
  </Directory>

  # Django - Specify the WSGI script, and ensure that our apps and 3rd-party
  # Python apps can be imported.

  #WSGIDaemonProcess coralnet python-path=/srv/www/coralnet/project:/srv/www/virtenv_coralnet/lib/python2.7/site-packages
  #WSGIProcessGroup coralnet
  #WSGIScriptAlias / /srv/www/coralnet/project/config/wsgi.py process-group=coralnet

  WSGIScriptAlias / /srv/www/coralnet/project/config/wsgi.py
  WSGIPythonPath /srv/www/coralnet/project:/srv/www/virtenv_coralnet/lib/python2.7/site-packages

  <Directory /srv/www/coralnet/project/config>
  <Files wsgi.py>
  Require all granted
  </Files>
  </Directory>

  # Allow mod_wsgi to use daemon mode on this system.
  # http://modwsgi.readthedocs.io/en/develop/user-guides/configuration-issues.html#location-of-unix-sockets

  #WSGISocketPrefix run/wsgi

We kept getting this 500 error when loading any page: ``ImproperlyConfigured: Error loading psycopg2 module: /srv/www/virtenv_coralnet/lib/python2.7/site-packages/psycopg2/_psycopg.so: undefined symbol: PyUnicodeUCS2_AsUTF8String``

`An SO thread <http://stackoverflow.com/questions/36129828/improperlyconfigured-error-importing-middleware-django-wsgi-error-apache>`__ suggested specifying ``WSGIPythonHome`` in the Apache config to explicitly point to the virtualenv's Python.

However, when we did this, we got a different error:

::

  ...
    File "/ ... /python2.7/hmac.py", line 8, in <module>
      from operator import _compare_digest as compare_digest
  ImportError: cannot import name _compare_digest

`This SO thread <http://stackoverflow.com/questions/24853027/django-importerror-cannot-import-name-compare-digest>`__ suggested recreating the virtualenv. However, when we did that, we were stuck with the same error.

Some possible troubleshooting steps from here include:

- Try apache + mod_wsgi with coralnet and a virtualenv based on the system's default Python (which is outdated, 2.7.6).
- Try apache + mod_wsgi with a bare Django project.
- Try apache + mod_wsgi with a Django project that's bare other than using PostgreSQL.


Tried Elastic Beanstalk, but didn't get it fully working (2016)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
According to Amazon, running a server through Elastic Beanstalk would allow the server resources to scale automatically according to actual load. However, configuration seems non-trivial to get right.

First, deploying EB with its Python framework is somewhat inflexible. It demands that the Python requirements file must be installed in ``requirements.txt`` at the root of the environment container. Up to this point, we haven't found a place to tell EB to run commands (such as ``cp config/requirements/production.txt requirements.txt``) prior to the Python packages being installed. So, we would have to manually copy the requirements.txt file over to the required location for purposes of deployment, and perhaps put this path in the ``.gitignore``. We haven't bothered getting this to work yet.

Besides that, there are numerous Linux packages that must be installed to get some of our Python packages working, particularly Pillow and psycopg2. These installations must be specified in EB's configuration files. However, to check if the EB configuration works, we have to deploy an EB instance, which takes around 5 minutes to complete. If we have one attempt at configuration every 5 minutes, we really need to know exactly what we're doing to maintain our sanity. We're probably not at this point yet.

One possible alternate route is to use EB's Dockerfile framework instead of its Python framework. This could potentially be easier to test outside of EB, and should offer more flexibility compared to EB's Python framework. It also ties most of our setup details to the popular Docker software rather than to EB.
