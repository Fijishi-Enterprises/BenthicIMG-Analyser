Production server setup
=======================
This page contains setup procedures for the AWS production server.


IAM user
-------------------------
Log into your AWS account and go to the Amazon IAM dashboard.

Create an IAM user. See `this Amazon docs page <http://docs.aws.amazon.com/AWSEC2/latest/UserGuide/get-set-up-for-amazon-ec2.html#create-an-iam-user>`__ for details.

Now you can log into AWS using your IAM user credentials, rather than your Amazon account credentials.


RDS instance
------------
Go to the Amazon EC2 dashboard. Create a Security Group which allows inbound connections on port 5432 (PostgreSQL) from the machine you are working from. (Use a site like `whatismyip.com <https://www.whatismyip.com/>`__ to find your IP.)

Go to the Amazon RDS dashboard. Create a PostgreSQL 9.5.x RDS instance.

- Assign the Security Group that you just created.
- Select Yes on the Publicly Accessible option.
- Make sure the Database Port is the default, 5432.

Once the RDS instance is created, in your local pgAdmin, log in as the master user you created.

Now using pgAdmin, follow the Installation page's :ref:`installation-postgresql` section to set up the ``coralnet`` database and ``django`` user.

- The ``coralnet`` database is already created, but needs the correct settings. Also, set ``django`` as the owner of the ``coralnet`` database, and as the owner of the ``public`` schema within ``coralnet``.

If doing the 2016 migration process:

- Edit the Security Group to also allow port-5432 connections from the machine running pgloader.
- Follow the instructions at this section: :ref:`y2016-migration-pgloader`


S3 bucket
---------
Go to the Amazon S3 console. Create a bucket.

Click your bucket's name, then click Properties, then Permissions. Click "Add bucket policy" and add the following policy:

::

  {
    "Version":"2012-10-17",
    "Statement":[
      {
        "Sid":"AddPerm",
        "Effect":"Allow",
        "Principal": "*",
        "Action":["s3:GetObject"],
        "Resource":["arn:aws:s3:::bucket-name-goes-here/*"]
      }
    ]
  }
  
- Replace ``bucket-name-goes-here`` with your bucket's name.

Click "Add CORS Configuration" and accept the default configuration.

When you have CoralNet up and running with S3, you may notice that the URLs of S3 bucket objects will contain an AWS access key ID, even when anonymous users view the objects. This is normal and does not seem to be a security issue, since an attacker cannot do anything unless they have the secret key as well. (`Link <http://stackoverflow.com/questions/7678835/how-secure-are-amazon-aws-access-keys>`__)


EC2 Linux instance
------------------
Go to the Amazon EC2 dashboard. Create a Security Group which allows:

- Inbound SSH connections (port 22) from the machine you are working from. (Use a site like `whatismyip.com <https://www.whatismyip.com/>`__ to find your IP.)
- Inbound HTTP and HTTPS connections from all IPs.

Use the dashboard to create a new EC2 instance.

Edit the RDS instance's Security Group to allow inbound connections from the EC2 instance's Security Group. (This allows Django to connect to the database.) In the Source box, type ``sg`` and the security group choices should appear.

Create a key pair for your IAM user if you haven't already, and SSH into the EC2 instance using the key pair.

- See `this Amazon docs page <http://docs.aws.amazon.com/AWSEC2/latest/UserGuide/get-set-up-for-amazon-ec2.html#create-a-key-pair>`__ for details on creating and configuring the key pair.
- Check the instance on the EC2 dashboard, and find its Public DNS. Use that as the host name to SSH into.
- The default username on the EC2 instance varies depending on which Linux you're using: `Link <http://docs.aws.amazon.com/AWSEC2/latest/UserGuide/TroubleshootingInstancesConnecting.html#TroubleshootingInstancesConnectingPuTTY>`__

Once you're in the SSH session, upgrade system packages: ``sudo apt-get update`` then ``sudo apt-get upgrade`` on Ubuntu. Log out. Go to the EC2 dashboard and reboot the EC2 instance. Log in again.

Create a ``/srv/www`` directory for putting website files. (This seems to be a recommended, standard location: `Link 1 <http://serverfault.com/questions/102569/should-websites-live-in-var-or-usr-according-to-recommended-usage>`__, `Link 2 <http://superuser.com/questions/635289/what-is-the-recommended-directory-to-store-website-content>`__)

- Change the directory's group to ``www-data``: ``sudo chgrp www-data www``
- Add your user to the ``www-data`` group: ``sudo usermod -aG www-data usernamegoeshere``
- Check that you did it right: ``cat /etc/group``
- If you are currently signed in as that user, logout and login to make the new permissions take effect. (`Source <http://unix.stackexchange.com/questions/96343/how-to-take-effect-usermod-command-without-logout-and-login>`__)
- Allow group write permissions: ``sudo chmod g+w www``
- Make all new files created in the ``www`` directory have their group set to the directory's group: ``sudo chmod g+s www``

Follow the :doc:`installation` page, putting the project files in ``/srv/www``. Make these adjustments to the instructions:

- Skip the PostgreSQL section; that was for the RDS instance, not this instance
- The Django ``DATABASES`` setting should match the RDS instance configuration
- If doing the 2016 migration process, go here for Django migration instructions: :ref:`y2016-migration-django-migrations`
- Skip the sections marked "(dev only)"
- When running ``runserver``, use an `SSH tunnel <http://www.sotechdesign.com.au/browsing-the-web-through-a-ssh-tunnel-with-firefox-and-putty-windows/>`__ to view the website. Make sure your browser's proxy settings do NOT exclude localhost or 127.0.0.1 from the SSH tunnel.


Web server
----------
Our current web server setup involves running gunicorn and nginx on the EC2 instance.

gunicorn
........
Activate your virtualenv. If you used the production requirements file, you should already have gunicorn installed. If not, run ``pip install gunicorn``.

``cd /srv/www/coralnet/project``. Change your Django settings to ``DEBUG = True`` for a start. Run ``gunicorn config.wsgi:application``. Check 127.0.0.1:8000 from an SSH tunnel to see if it worked.

Now change your Django settings to ``DEBUG = False``, and then run the same command: ``gunicorn config.wsgi:application``. Check 127.0.0.1:8000 from an SSH tunnel to see if loading pages works. If you want to make things easier for now, change two Django settings: ``ADMINS = []`` and ``ALLOWED_HOSTS = [<other entries>, '127.0.0.1']``.


nginx
.....
``sudo apt-get install nginx``.

Run ``sudo /etc/init.d/nginx start``. On your local machine, try entering the EC2 instance's public DNS in your browser's address bar. You should see a "Welcome to nginx!" page.

Allow nginx to find our configuration file, enable it, and disabled the default site's configuration file (`Source <http://serverfault.com/a/424456>`__):

::

  sudo ln -s /srv/www/coralnet/project/config/nginx.conf /etc/nginx/sites-available/coralnet
  sudo ln -s /etc/nginx/sites-available/coralnet /etc/nginx/sites-enabled
  sudo rm /etc/nginx/sites-enabled/default
  
- Try browsing `the nginx docs <http://nginx.org/en/docs/beginners_guide.html>`__ if you're wondering how nginx config works.

Restart nginx: ``sudo /etc/init.d/nginx restart``.

Run gunicorn, this time binding it to localhost on port 8001, and setting a longer timeout than the default 30s: ``gunicorn config.wsgi:application --bind=127.0.0.1:8001 --timeout 200``

Again, on your local machine, enter the EC2 instance's public DNS in your browser's address bar. You should see the CoralNet website.

From here on out:

- Remember that you need both nginx and gunicorn up and running for the website to work.
- To update the website code, kill the gunicorn process, then update the code, then start gunicorn again.
- Remember that gunicorn must be run in the virtualenv.


Apache (old)
............
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


mod_wsgi (old)
..............
Get mod_wsgi from the source code link `here <https://modwsgi.readthedocs.io/en/develop/user-guides/quick-installation-guide.html>`__. Extract it.

``cd`` into the extracted mod_wsgi directory, and run:

::
    
  ./configure
  make
  sudo make install

Locate the Apache config file, such as ``/usr/local/apache2/conf/httpd.conf``. Add this line to the file, at the same point that other Apache modules are being loaded: ``LoadModule wsgi_module /usr/lib/apache2/modules/mod_wsgi.so`` (Edit the last option according to where ``mod_wsgi.so`` is located.)


Django configuration of Apache + mod_wsgi (old)
...............................................
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
  
    File "/ ... /python2.7/hmac.py", line 8, in <module>
      from operator import _compare_digest as compare_digest
  ImportError: cannot import name _compare_digest

`This SO thread <http://stackoverflow.com/questions/24853027/django-importerror-cannot-import-name-compare-digest>`__ suggested recreating the virtualenv. However, when we did that, we were stuck with the same error.

Some possible troubleshooting steps from here include:

- Try apache + mod_wsgi with coralnet and a virtualenv based on the system's default Python (which is outdated, 2.7.6).
- Try apache + mod_wsgi with a bare Django project.
- Try apache + mod_wsgi with a Django project that's bare other than using PostgreSQL.


Elastic Beanstalk (old)
.......................
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
