.. _web_server:

Web server
==========


Running the runserver command
-----------------------------
- *Development server*
- *Staging server*

Ensure your virtualenv is activated, and run ``python manage.py runserver`` from the ``project`` directory.

Navigate to your localhost web server, e.g. ``http://127.0.0.1:8000/``, in your browser.

- When running a staging server on an EC2 instance, use an `SSH tunnel <http://www.sotechdesign.com.au/browsing-the-web-through-a-ssh-tunnel-with-firefox-and-putty-windows/>`__ to view the website. Make sure your browser's proxy settings do NOT exclude localhost or 127.0.0.1 from the SSH tunnel.


What to test
------------
- *Development server*
- *Staging server*

Register and activate a user using the website's views. If you're using the development server, you should see the activation email in the console running Django. If you're using the staging server, the activation email should be in the directory specified by the ``EMAIL_FILE_PATH`` setting.

Try creating a source, uploading images, making a labelset, making annotations, checking annotation history, and browsing patches. Test any other pages that come to mind.

If you don't have a superuser yet, use ``python manage.py createsuperuser`` to create one. Log in as a superuser and try checking out the admin interface at ``<site domain>/admin/``.

(TODO: Vision backend testing)


Using gunicorn and nginx
------------------------
- *Production server*

gunicorn
~~~~~~~~
Activate your virtualenv. If you used the production requirements file, you should already have gunicorn installed. If not, run ``pip install gunicorn``.

``cd /path/to/coralnet/project``. Change your Django settings file to ``DEBUG = True`` temporarily for testing. Run ``gunicorn config.wsgi:application``. Check 127.0.0.1:8000 from an SSH tunnel to see if it worked.

Now change your Django settings to ``DEBUG = False``, and then run the same command: ``gunicorn config.wsgi:application``. Check 127.0.0.1:8000 from an SSH tunnel to see if loading pages works. If you get "The connection was reset" in Firefox or similar, you can change the ``ALLOWED_HOSTS`` setting to ``[]`` for the moment.


nginx
~~~~~
(Pronounced `"engine x" <http://nginx.org/en/>`__.)

``sudo apt-get install nginx``.

Run ``sudo /etc/init.d/nginx start``. On your local machine, try entering the EC2 instance's public DNS in your browser's address bar. You should see a "Welcome to nginx!" page.

Allow nginx to find our configuration file, enable our config, and disable the default site's configuration file (`Source <http://serverfault.com/a/424456>`__):

::

  sudo ln -s /path/to/coralnet/project/config/nginx.conf /etc/nginx/sites-available/coralnet
  sudo ln -s /etc/nginx/sites-available/coralnet /etc/nginx/sites-enabled
  sudo rm /etc/nginx/sites-enabled/default

- Try browsing `the nginx docs <http://nginx.org/en/docs/beginners_guide.html>`__ if you're wondering how nginx config works.


Running
~~~~~~~
If this is the first time running, or the nginx config template has been updated, run ``python manage.py makenginxconfig``.

Restart nginx: ``sudo /etc/init.d/nginx restart``. (Other commands are ``start``, ``stop``, and ``status``.)

Run gunicorn. This time we'll use our gunicorn config file, which binds to localhost on the port that our nginx config expects. We'll also add `&` at the end to run it as a background process: ``gunicorn config.wsgi:application --config=config/gunicorn.py &``

Again, on your local machine, enter the EC2 instance's public DNS in your browser's address bar. You should see the CoralNet website.

From here on out:

- Remember that you need both nginx and gunicorn up and running for the website to work.
- To update the Django code, kill the gunicorn master process, then update the code, then start gunicorn again. :ref:`Scripts <scripts>` can help make the process easier.
- Remember that gunicorn must be run in the virtualenv, and also run from the correct directory (``coralnet/project``) so that ``config.wsgi`` and ``config/gunicorn.py`` can be found.


.. _tls:

HTTPS/SSL/TLS
-------------
- *Production server*

SSL/TLS is an important security addition to any website. It encrypts communication between the user and web server, so that sensitive information such as user passwords aren't sent over the network in plain text. SSL/TLS also prevents site spoofing (to varying extents, depending on the exact SSL/TLS configuration).

Get a free TLS certificate using `Let's Encrypt <https://letsencrypt.org/getting-started/>`__:

- Enlarge the SSH window to at least 132x43 to avoid a DialogError while running the certbot (`Source <https://github.com/certbot/certbot/issues/2787>`__)
- In nginx, turn off the coralnet site, and turn on the default nginx site. This makes it easier to use Let's Encrypt's webroot option.

  - ``sudo ln -s /etc/nginx/sites-available/default /etc/nginx/sites-enabled``
  - ``sudo rm /etc/nginx/sites-enabled/coralnet``
  - ``sudo /etc/init.d/nginx restart``
  - Ensure you see the default nginx page at the website URL

- Ensure that the server allows all IPs on port 80 and 443
- ``sudo apt-get install letsencrypt``
- ``letsencrypt certonly --webroot -w /usr/share/nginx/html -d <domain (FQDN)>``
- Enter email address if prompted
- Agree to TOS if prompted
- Turn the coralnet site back on

  - ``sudo ln -s /etc/nginx/sites-available/coralnet /etc/nginx/sites-enabled``
  - ``sudo rm /etc/nginx/sites-enabled/default``
  - ``sudo /etc/init.d/nginx restart``
  - Ensure you see the coralnet website at our website URL

Notes:

- Let's Encrypt certificates expire after 3 months. So either get set up with their system of certificate auto-renewal, or remember to make a new certificate before the 3 months are up (there is a reminder-email option).
- Let's Encrypt issues "domain-validated" TLS certificates. There are `different levels of TLS certificates <http://security.stackexchange.com/questions/13453/are-all-ssl-certificates-equal>`__, although whether those levels matter for security is up for debate.
- LE seems to reject all EC2 domains as part of its policy. `Link <https://community.letsencrypt.org/t/policy-forbids-issuing-for-name-on-amazon-ec2-domain/12692>`__ - "amazonaws.com happens to be on the blacklist Let's Encrypt uses for high-risk domain names (i.e. phishing targets, etc.)."


.. _postfix:

Email server - Postfix
----------------------
- *Production server*

Postfix seems to be recommended for a simple outgoing-only mail server.

- Enlarge the SSH window as much as you can so the install choices aren't invisible to you. (If you messed up here, force kill the SSH session and try again.)
- Run: ``sudo apt-get install postfix``
- Choose "Internet site: Mail is sent and received directly using SMTP."
- FQDN: e.g. ``subdomain.example.com``

To add our SSL certificate, open ``/etc/postfix/main.cf`` with sudo, and add or edit the following lines:

::

  smtp_tls_cert_file=/etc/letsencrypt/live/<FQDN goes here>/fullchain.pem
  smtp_tls_key_file=/etc/letsencrypt/live/<FQDN goes here>/privkey.pem
  smtpd_tls_cert_file=/etc/letsencrypt/live/<FQDN goes here>/fullchain.pem
  smtpd_tls_key_file=/etc/letsencrypt/live/<FQDN goes here>/privkey.pem
  smtp_use_tls=yes

Then run ``sudo /etc/init.d/postfix reload``.

Try sending mail from the website (e.g. by requesting a password reset) to a Gmail account. When that mail is opened in Gmail, there should not be a red padlock next to the email sender. (A red padlock would indicate a lack of TLS/SSL.)


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


Getting the latest nginx
------------------------
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



Previous failed attempts at web server setup
--------------------------------------------

This section documents some different web server software setups that haven't worked for us in the past.


Apache + mod_wsgi
~~~~~~~~~~~~~~~~~
The CoralNet production server used Apache and mod_wsgi from the beginning of the site's life until the server problems in 2016.06. When trying to set up Apache and mod_wsgi again after that, we couldn't get it to work again. However, there are no confirmed benefits for using this setup over gunicorn + nginx (which we have figured out), so this may not be a big loss.


Apache
......
The following is based on `Apache's installation guide <https://httpd.apache.org/docs/2.4/install.html>`__.

Download PCRE from `here <http://www.pcre.org/>`__. Extract it.

- These instructions include PCRE 1, not 2. Using 2 seems to get stuck at the httpd ``make`` step, as it tries to find ``pcre.h`` while the file you have is ``pcre2.h``.

``cd`` into the extracted PCRE directory, and run:

::

  ./configure
  make
  sudo make install

Download Apache httpd from their `website <http://httpd.apache.org/download.cgi>`__. Extract it.

Download Apache Portable Runtime (APR) from `here <http://apr.apache.org/>`__. Extract it into ``srclib/apr`` under the ``httpd`` source tree that you just extracted. For example: ``tar xzvf apr-1.5.2.tar.gz -C httpd-2.4.20/srclib`` then ``mv httpd-2.4.20/srclib/apr-1.5.2 httpd-2.4.20/srclib/apr``.

Download APR-Util from the same page. Extract it into ``srclib/apr-util`` under the ``httpd`` source tree. For example: ``tar xzvf apr-util-1.5.4.tar.gz -C httpd-2.4.20/srclib`` then ``mv httpd-2.4.20/srclib/apr-util-1.5.4 httpd-2.4.20/srclib/apr-util``.

Now ``cd`` into the ``httpd`` directory, and run:

::

  ./configure --with-included-apr
  make
  sudo make install

Also get:

- The dev package for Apache: ``sudo apt-get install apache2-dev`` on Ubuntu.
- The ``lynx`` text-based browser, which allows you to see Apache's status: ``sudo apt-get install lynx`` on Ubuntu.

You may want to add the directory containing ``apachectl`` to the ``PATH`` environment variable. To modify the ``PATH`` that a sudoer sees on Ubuntu, run ``sudo visudo`` and modify the ``secure_path`` line. (`Source <http://stackoverflow.com/a/4572018>`__)


mod_wsgi
........
Get mod_wsgi from the source code link `here <https://modwsgi.readthedocs.io/en/develop/user-guides/quick-installation-guide.html>`__. Extract it.

``cd`` into the extracted mod_wsgi directory, and run:

::

  ./configure
  make
  sudo make install

Locate the Apache config file, such as ``/usr/local/apache2/conf/httpd.conf``. Add this line to the file, at the same point that other Apache modules are being loaded: ``LoadModule wsgi_module /usr/lib/apache2/modules/mod_wsgi.so`` (Edit the last option according to where ``mod_wsgi.so`` is located.)


Django configuration of Apache + mod_wsgi
.........................................
Edit ``httpd.conf`` to include:

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


Why Apache + mod_wsgi was a dead end so far
...........................................
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


Elastic Beanstalk
~~~~~~~~~~~~~~~~~
According to Amazon, running a server through Elastic Beanstalk would allow the server resources to scale automatically according to actual load. However, configuration seems non-trivial to get right, and we haven't managed it yet.

These instructions are mainly from the `tutorial on deploying Django with Elastic Beanstalk <https://docs.aws.amazon.com/elasticbeanstalk/latest/dg/create-deploy-python-django.html>`__.

In your EC2 instance, install the Elastic Beanstalk command-line interface: ``sudo pip install awsebcli``

``cd /srv/www/coralnet/project`` then ``eb init -p python2.7 coralnet``. It'll ask for credentials. Check the IAM Dashboard under Security Credentials for the access ID. It won't let you view the secret key again though; you'll need to have that saved.

- The directory you run ``eb init`` in will end up having an ``.elasticbeanstalk`` directory.

If you want to be able to SSH into the instance running your application, run ``eb init`` again and select your keypair at the prompt.

``eb create coralnet-env`` to create a load-balanced Elastic Beanstalk environment. This will take about 5 minutes to complete.

Check ``eb status``. The ``CNAME`` is a public URL for the website. Copy and paste it into your browser's URL bar to see the website.

- You can also find the EB environment's URL with the Elastic Beanstalk dashboard.

- To get a better handle on what has been deployed, you can go to the EB dashboard and look under Application Versions for your EB application. Click a Source archive to download it.

- To get a better handle on the deployed environment's status, click the environment in the EB dashboard. (Should be a green box, or a different color depending on the "health" of the environment.)

- To see logs, try ``eb logs`` or go to the EB dashboard to view the environment's Logs. ``error_log`` should have info for 500 errors.

- From now on, after you change any code, you'll be able to re-deploy the website using ``eb deploy``.


Why Elastic Beanstalk didn't work out so far
............................................
Deploying EB with its Python framework is somewhat inflexible. It demands that the Python requirements file must be installed in ``requirements.txt`` at the root of the environment container. Up to this point, we haven't found a place to tell EB to run commands (such as ``cp config/requirements/production.txt requirements.txt``) prior to the Python packages being installed. So, we would have to manually copy the requirements.txt file over to the required location for purposes of deployment, and perhaps put this path in the ``.gitignore``. We haven't bothered getting this to work yet.

Besides that, there are numerous Linux packages that must be installed to get some of our Python packages working, particularly Pillow and psycopg2. These installations must be specified in EB's configuration files. However, to check if the EB configuration works, we have to deploy an EB instance, which takes around 5 minutes to complete. If we have one attempt at configuration every 5 minutes, we really need to know exactly what we're doing to maintain our sanity. We're probably not at this point yet.

One possible alternate route is to use EB's Dockerfile framework instead of its Python framework. This could potentially be easier to test outside of EB, and should offer more flexibility compared to EB's Python framework. It also ties most of our setup details to the popular Docker software rather than to EB.