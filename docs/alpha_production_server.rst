Alpha production server
=======================
This page contains miscellanous notes about the old alpha production server - a physical server machine running Linux.


Linux
-----
- We started off using a standard GUI version of Ubuntu.
- Around October 2014 we switched to Ubuntu Server 11.04 (command line only) since the xserver of the previous install started having problems.
- Starting from the 2016/06 restore we used Ubuntu Server 14.04.


Git
-----
Note that Git tracks changes of Linux file permissions.

After doing the 2016/06 restore, we had the repo files in place before even installing git, and ended up changing the permissions of some of those files while setting things up. Then ``git status`` showed a lot of unstaged changes. This took us by surprise, but we managed to get out of the mess by carefully using ``diff`` to check which files had a permissions mode change as the only change, and reverting those files.


Python
------
Starting from the 2016/06 restore, we used Python 2.7.11.

Details on installations we needed in Ubuntu Server 14.04 to get Python set up properly:

- ``sudo apt-get install gcc``
- ``sudo apt-get install make``
- At this point, if you build Python, you should see a message ``Python build finished, but the necessary bits to build these modules were not found:`` followed by a bunch of packages.

  - Here is a list of what we installed with apt-get to trim down the not-found packages:
  
    - zlib1g-dev (matches the already-installed zlib1g)
    - libncurses5-dev (matches the already-installed libncurses5)
    - libsqlite3-dev (matches the already-installed libsqlite3-0)
    - libbz2-dev (best match for the already-installed libbz2-1.0)
    - libreadline6-dev (matches the already-installed libreadline6)
    - libssl-dev (best match for the already-installed libssl1.0.0)
    - libdb5.3-dev (matches the already-installed libdb5.3. This is a package to support the Oracle Berkeley DB)
    - libgdbm-dev (best match for the already-installed libgdbm3)
    
  - At this point we only had the following packages not found, which are all unnecessary as noted in `this gist.github link <https://gist.github.com/reorx/4067217>`__:
  
    - bsddb185: Older version of Oracle Berkeley DB. Undocumented. Install version 4.8 instead.
    - dl: For 32-bit machines. Deprecated. Use ctypes instead.
    - imageop: For 32-bit machines. Deprecated. Use PIL instead.
    - sunaudiodev: For Sun hardware. Deprecated.
    - _tkinter: For tkinter graphy library, unnecessary if you don't develop tkinter programs.
    
  - `This link <http://rajaseelan.com/2012/01/28/installing-python-2-dot-7-2-on-centos-5-dot-2/>`__ was also useful for confirming what to do in this step.
  - If you have to fix installations for the ``make`` step, don't forget to rerun the ``make altinstall`` as well.
  
- pip: Do a wget of ``get-pip.py`` as linked in `pip's docs <https://pip.pypa.io/en/latest/installing/>`__. Then run ``sudo /usr/local/bin/python2.7 get-pip.py``. As of the 2016/06 restore, this installed pip 8.1.2.

We made a virtualenv for the 2016/06 restore, but didn't end up using it because MATLAB apparently might have required running the Python part of the server with sudo. Wasn't sure how sudo and virtualenv were supposed to work together, so we just went without a virtualenv.

Python packages and versions as of the 2016/06 restore (since we aren't documenting these in a requirements.txt). Note that Sentry only showed package versions for packages that are added in Django's installed apps, so we couldn't check exact versions of other packages like numpy:

- MySQL-python==1.2.5 (picked 1.2.x from memory)

  - https://pypi.python.org/pypi/MySQL-python/1.2.5 "MySQL-3.23 through 5.5 and Python-2.4 through 2.7 are currently supported."
  - First do an apt-get install of libmysqlclient-dev (already had libmysqlclient18) (`Source <http://stackoverflow.com/questions/5178292/>`__)
  
- Pillow==2.1.0 (mentioned in our old repo's wiki: "As the Pillow page says (as of Pillow 2.1.0) ...")
- numpy==1.11.0 (latest version)
- django==1.3.0 (matches a pre-2016/06 Sentry log)

  - This had to be installed like: ``pip install --no-binary django django==1.3.0`` (`Source <http://stackoverflow.com/questions/31009216/>`__). Otherwise the admin templates would be missing for some reason. For us, this was only required for one of the virtualenv or non-virtualenv installs, but not the other. Forgot which was which.
    
- django-guardian==1.0.2 (matches a pre-2016/06 Sentry log)
- easy-thumbnails==1.0.3 (matches a pre-2016/06 Sentry log)
- django-userena==1.0.1 (matches our old repo's docs)
- South==0.7.6 (a pre-2016/06 Sentry log has 0.7.3)
- django-reversion==1.5.1 (matches a pre-2016/06 Sentry log)
- django-sentry==1.8.6.2 (matches a pre-2016/06 Sentry log)
- django-dajaxice==0.2 (matches a pre-2016/06 Sentry log)

  - Had to manually get this from the PyPI website; not auto-downloadable through pip
  
- django-dajax==0.8.4 (matches a pre-2016/06 Sentry log)

  - Had to manually get this from the PyPI website; not auto-downloadable through pip
  
- GChartWrapper==0.9 (version picked from memory, and also the latest version)

  - Had to manually get this from the PyPI website; not auto-downloadable through pip
  
- PyYAML==3.11 (latest version)
- django-supervisor==0.3.2 (a pre-2016/06 Sentry log has 0.3.0)


Mail server
-----------
Postfix seems to be recommended for a simple outgoing-only mail server. Run: ``sudo apt-get install postfix``

- Choose "Internet site: Mail is sent and received directly using SMTP."
- FQDN: e.g. ``subdomain.example.com``

It's important to send encrypted mail, especially during the signup procedure. Get a free TLS certificate using `Let's Encrypt <https://letsencrypt.org/getting-started/>`__.

- Note that Let's Encrypt certificates expire after 3 months. So either get set up with their system of certificate auto-renewal, or remember to make a new certificate before the 3 months are up.
- Let's Encrypt issues "domain-validated" TLS certificates. There are `different levels of TLS certificates <http://security.stackexchange.com/questions/13453/are-all-ssl-certificates-equal>`__, although whether those levels matter for security is up for debate.
- Our specific procedure to get a Let's Encrypt certificate:

  - Enlarge the SSH window to at least 132x43 to avoid a DialogError while running the certbot (`Source <https://github.com/certbot/certbot/issues/2787>`__)
  - In nginx, turn off the coralnet site, and turn on the default nginx site
  
    - ``sudo ln -s /etc/nginx/sites-available/default /etc/nginx/sites-enabled``
    - ``sudo rm /etc/nginx/sites-enabled/coralnet``
    - ``sudo /etc/init.d/nginx restart``
    - Ensure you see the default nginx page at the website URL
    
  - Ensure that the server allows all IPs on port 80
  - ``wget https://dl.eff.org/certbot-auto``
  - ``chmod a+x certbot-auto``
  - ``./certbot-auto certonly --webroot-path /usr/share/nginx/html``, select webroot option, enter email, agree, enter FQDN
  - Turn the coralnet site back on
  
    - ``sudo ln -s /etc/nginx/sites-available/coralnet /etc/nginx/sites-enabled``
    - ``sudo rm /etc/nginx/sites-enabled/default``
    - ``sudo /etc/init.d/nginx restart``
    - Ensure you see the coralnet website at the website URL
    
Now that we have a certificate, add or edit in the following lines in ``/etc/postfix/main.cf``:

::

  smtp_tls_cert_file=/etc/letsencrypt/live/<FQDN goes here>/privkey.pem
  smtp_tls_key_file=/etc/letsencrypt/live/<FQDN goes here>/fullchain.pem
  smtpd_tls_cert_file=/etc/letsencrypt/live/<FQDN goes here>/privkey.pem
  smtpd_tls_key_file=/etc/letsencrypt/live/<FQDN goes here>/fullchain.pem
  
Then run ``sudo /etc/init.d/postfix reload``, and try sending mail from the website (e.g. using the website's Contact Us page) to a Gmail account. When that mail is opened in Gmail, there should not be a red padlock next to the email sender. (A red padlock would indicate a lack of TLS/SSL.)


Things to change after a suspected breach
-----------------------------------------
High priority:

- Ubuntu passwords
- Database passwords, especially the password Django uses to authenticate

Medium priority:

- Website admins' passwords (can also revoke admin status from inactive admins)
- Other users' passwords (tell them to change their passwords)
- Django secret key
- SSH key from the server machine to GitHub (can be revoked from GitHub's website)

Lower priority:

- Google Maps API key
- Recaptcha keys


Other gritty details
--------------------------------------
- The Python install we're using is in ``/usr/local/bin`` and ``/usr/local/lib``.
- The non-symlink cnhome directory must be named ``CoralNet`` to satisfy bad imports like ``CoralNet.exceptions``. (These imports exist because we have stuff like ``exceptions.py`` at the root of our project.)
