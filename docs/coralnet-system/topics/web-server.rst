Web server software setup
=========================


gunicorn
--------
Activate your virtualenv. If you used the production requirements file, you should already have gunicorn installed. If not, run ``pip install gunicorn``.

``cd /path/to/coralnet/project``. Change your Django settings file to ``DEBUG = True`` temporarily for testing. Run ``gunicorn config.wsgi:application``. Check 127.0.0.1:8000 from an SSH tunnel to see if it worked.

Now change your Django settings to ``DEBUG = False``, and then run the same command: ``gunicorn config.wsgi:application``. Check 127.0.0.1:8000 from an SSH tunnel to see if loading pages works. If you get "The connection was reset" in Firefox or similar, you can change the ``ALLOWED_HOSTS`` setting to ``[]`` for the moment.


nginx
-----
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
-------
If this is the first time running, or the nginx config template has been updated, run ``python manage.py makenginxconfig``.

Restart nginx: ``sudo /etc/init.d/nginx restart``. (Other commands are ``start``, ``stop``, and ``status``.)

Run gunicorn. This time we'll use our gunicorn config file, which binds to localhost on the port that our nginx config expects. We'll also add `&` at the end to run it as a background process: ``gunicorn config.wsgi:application --config=config/gunicorn.py &``

Again, on your local machine, enter the EC2 instance's public DNS in your browser's address bar. You should see the CoralNet website.

From here on out:

- Remember that you need both nginx and gunicorn up and running for the website to work.
- To update the Django code, kill the gunicorn master process, then update the code, then start gunicorn again. :ref:`Scripts <server-scripts>` can help make the process easier.
- Remember that gunicorn must be run in the virtualenv, and also run from the correct directory (``coralnet/project``) so that ``config.wsgi`` and ``config/gunicorn.py`` can be found.


HTTPS/SSL/TLS (Production only)
-------------------------------

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
- ``sudo letsencrypt certonly --webroot -w /var/www/html -d <domain (FQDN)>``

  - An example of ``<domain (FQDN)>`` would be ``coralnet.ucsd.edu``.
  - ``/var/www/html`` should be whatever the ``root`` directive specifies in the nginx config file ``/etc/nginx/sites-available/default``.
  - ``sudo`` is needed so that it can write to the Let's Encrypt log directory.

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


Email server - Postfix (Production only)
----------------------------------------
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
