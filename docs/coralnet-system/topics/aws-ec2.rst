Amazon EC2 instance setup with CoralNet installation
====================================================


Creating an EC2 instance
------------------------

First ensure you've :doc:`created a key pair <aws-auth>` to authenticate with EC2 instances.

Ensure you've created a Security Group which allows:

- Inbound SSH connections (port 22) from the machine you are working from. (Use a site like `whatismyip.com <https://www.whatismyip.com/>`__ to find your IP.)
- Inbound HTTP (port 80) and HTTPS (port 443) connections from all IPs.

Use the EC2 console to create a new EC2 instance:

- Pick an instance type.

- On the "Configure Instance Details" step:

  - Disable "Auto-assign public IP".

    - Amazon's help text says to use this "If you require a persistent public IP address that you can associate and disassociate at will", as opposed to a "public IP address associated with the instance until it’s stopped or terminated, after which it’s no longer available for you to use".

  - Select an IAM role which has the policies ``AmazonS3FullAccess`` and ``AmazonSQSFullAccess``.

    - By associating the EC2 instance with an IAM role, the instance's ``secrets.json`` file doesn't have to specify AWS credentials.

    - Careful to not skip this: associating an IAM role with an *existing* instance isn't possible. There are only workarounds. (`Link 1 <http://stackoverflow.com/questions/23416502/>`__, `Link 2 <https://aws.amazon.com/iam/faqs/>`__)

  - Ensure shutdown behavior is "Stop".

  - Check "Protect against accidental termination".

    - This ensures that two distinct steps are required to terminate the EC2 instance: disable the instance's termination protection, and delete the instance.

  - (TODO: Enable CloudWatch? `Additional charges apply <https://aws.amazon.com/cloudwatch/pricing/>`__.)

- On the "Add Storage" step, uncheck "Delete on Termination".

- On the "Configure Security Group" step, choose the previously created Security Group.

- Launch the instance. Upon clicking "Launch", associate a key pair that you have control over. This key pair will be used to authenticate with the default user (e.g. the ``ubuntu`` user for an Ubuntu Linux instance).

- Associate an Elastic IP with the instance. (Production only, not staging)

  - Create an Elastic IP (also in the EC2 console) if you don't have one.

  - Select your Elastic IP, then Actions -> Associate Address. Select your new EC2 instance.

On the list of instances, give your new instance a descriptive name.

Edit the RDS instance's Security Group to allow inbound connections from the EC2 instance's Security Group. (This allows Django to connect to the database.) In the Source box, type ``sg`` and the security group choices should appear.

SSH into the EC2 instance using the key pair, and confirm that it works.

- Check the instance on the EC2 dashboard, and find its Public DNS. Use that as the host name to SSH into.
- Log in with the EC2 instance's default username. The username varies depending on which Linux you're using (it's ``ubuntu`` for Ubuntu instances): `Link <http://docs.aws.amazon.com/AWSEC2/latest/UserGuide/TroubleshootingInstancesConnecting.html#TroubleshootingInstancesConnectingPuTTY>`__


Reserving an EC2 instance
^^^^^^^^^^^^^^^^^^^^^^^^^
Typically you are charged a certain rate for running an EC2 instance, and you're simply charged based on how long you run that instance.

There is also the option to reserve an EC2 instance. When you reserve an instance, you pay an upfront fee and get a lower cost rate. After the reservation term is over, this should result in less cost compared to not reserving the instance. Cost savings depend on the reservation type (no upfront, partial upfront, or all upfront), and range from roughly 30%-40% compared to no reservation.

In return, you must pay the rate until the end of the term, even if you stop using the instance before then.

Amazon gives this incentive to reserve instances because it gives them more information about what resources they need to give you in the long term.

A reservation's instance type (e.g. t2.medium) and availability zone (e.g. uswest2) are fixed, but the reservation can be applied to different instances throughout the reservation's lifetime.

`Link 1 <https://www.quora.com/What-is-the-concept-behind-reserved-instances-for-EC2>`__, `Link 2 <https://alestic.com/2014/12/ec2-reserved-instances/>`__, `Link 3 <https://skeddly.desk.com/customer/portal/articles/1348371-how-reserved-ec2-instances-work>`__


.. _aws-cli:

Setting up the AWS command line interface (CLI)
-----------------------------------------------
Install the AWS CLI: ``sudo apt-get install awscli``

Run ``aws configure``. You'll be prompted for the following:

- Just hit Enter on the Access Key ID and Secret Access Key prompts, since the instance is already associated with an IAM Role.
- For Default region name, enter our primary region, such as ``us-west-2``.
- Just hit Enter on the Default output format. This determines the formatting style for command output, but the default seems to work fine.


Adding users
------------
`This Amazon guide <http://docs.aws.amazon.com/AWSEC2/latest/UserGuide/managing-users.html>`__ explains that it's insecure to share the default user (we'll assume this is ``ubuntu`` for brevity) between multiple people, because "that account can cause a lot of damage to a system when used improperly." Therefore, we'll create a user per team member.

Log into the EC2 instance using the ``ubuntu`` user.

Do the following for each team member you want to add a user for:

- Create a user using ``sudo adduser <username> --disabled-password`` and then follow the rest of the instructions in the above guide. Ensure the user has their own key pair to use, and add the appropriate public key for that user.

  - See the "Retrieving the Public Key for your Key Pair ..." sections on `this Amazon guide <http://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-key-pairs.html>`__ to get your public key.

- Allow the user to use ``sudo`` without specifying a password (since requiring a private key login makes a password redundant):

  - Add the user to the sudoers group: ``sudo usermod -a -G sudo <username>``
  - Run ``sudo visudo -f /etc/sudoers.d/mysudoers`` to edit a new sudoers file called ``mysudoers``. Add the line: ``<username> ALL=NOPASSWD: ALL`` (`Source <http://superuser.com/a/869145/>`__).

    - If you are adding multiple users, just use the same sudoers file for both users.
    - FYI, the default ``ubuntu`` user doesn't require a sudo password by default. That's configured in ``/etc/sudoers.d/90-cloud-init-users``. (`Source <http://askubuntu.com/questions/309418/make-an-amazon-ec2-instance-ask-for-sudoing-password>`__) This is because the ``ubuntu`` user doesn't have a login password by default, since as previously mentioned, a private key requirement makes a password redundant.

Open another SSH session and log in with your personal new user. Try a ``sudo`` command. If it worked, you can close the SSH session of the default user (e.g. ``ubuntu``) and use your personal user from now on.


Initial update of Linux packages
--------------------------------
Upgrade system packages: ``sudo apt-get update`` then ``sudo apt-get upgrade`` on Ubuntu. Log out. Go to the EC2 dashboard and reboot the EC2 instance. Log in again.

  - Although it's not all that important in this case: "We recommend that you use Amazon EC2 to reboot your instance instead of running the operating system reboot command from your instance. If you use Amazon EC2 to reboot your instance, we perform a hard reboot if the instance does not cleanly shut down within four minutes. If you use AWS CloudTrail, then using Amazon EC2 to reboot your instance also creates an API record of when your instance was rebooted." (`Link <http://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-instance-reboot.html>`__)


Installing PostgreSQL client
----------------------------
When hosting the database on Amazon RDS, you won't need to install the PostgreSQL server software on the web server instance, but you'll need to install the PostgreSQL client software. The package should be ``postgresql-client-<version number>``. Get the package which matches the PostgreSQL-server version number.


Setting up www directory
------------------------

Create a ``/srv/www`` directory for putting website files. (This seems to be a recommended, standard location: `Link 1 <http://serverfault.com/questions/102569/should-websites-live-in-var-or-usr-according-to-recommended-usage>`__, `Link 2 <http://superuser.com/questions/635289/what-is-the-recommended-directory-to-store-website-content>`__)

- Change the directory's group to ``www-data``: ``sudo chgrp www-data www``
- Add your user to the ``www-data`` group: ``sudo usermod -aG www-data <username>``
- Check that you did it right: ``cat /etc/group``
- If you are currently signed in as that user, logout and login to make the new permissions take effect. (`Source <http://unix.stackexchange.com/questions/96343/how-to-take-effect-usermod-command-without-logout-and-login>`__)
- Allow group write permissions: ``sudo chmod g+w www``
- Make all new files created in the ``www`` directory have their group set to the directory's group: ``sudo chmod g+s www``


Setting up CoralNet project
---------------------------
Git clone the project to ``/srv/www``, such that the directory ``/srv/www/coralnet`` is the Git repository root.

Go through the following development-server installation sections:

- Python

  - If having trouble installing this, see the below subsection on specifics

- Python packages

  - Use ``requirements/production.txt`` for both production and staging

- Django settings module

  - Use ``production`` for production, ``staging`` to run staging via nginx, and ``staging_debug`` to run staging via runserver.

- secrets.json

- Creating necessary directories

- Running the unit tests

  - TODO: Review whether running these with production settings could have unwanted side effects. Until that's confirmed, limit unit tests to staging.

Do not proceed to Django migrations (this page doesn't cover RDS) or Running the web server (different for production, covered in another section).


Python 2.7.x installation specifics for Ubuntu Server
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Download and install the latest Python 2.7.x. 32 bit or 64 bit doesn't matter. It's perfectly fine to keep other Python versions on the same system. Just make sure that your ``python`` and ``pip`` commands point to the correct Python version.

- On Linux, you'll probably have to install this Python version from source.

  - You'll probably want to install some other packages first. Here's what was needed on Ubuntu Server 14.04 and 16.04:

    - ``sudo apt-get install gcc`` - to avoid getting ``configure: error: no acceptable C compiler found in $PATH``.
    - ``sudo apt-get install make`` - to avoid getting ``The program 'make' is currently not installed.``

    - When you run ``make`` during Python installation, you'll see a message ``Python build finished, but the necessary bits to build these modules were not found:`` followed by a list of components. Here is a list of things to install to trim down the not-found components:

      - ``sudo apt-get install zlib1g-dev`` (matches the already-installed zlib1g)
      - ``sudo apt-get install libncurses5-dev`` (matches the already-installed libncurses5)
      - ``sudo apt-get install libsqlite3-dev`` (matches the already-installed libsqlite3-0)
      - ``sudo apt-get install libbz2-dev`` (best match for the already-installed libbz2-1.0)
      - ``sudo apt-get install libreadline6-dev`` (matches the already-installed libreadline6)
      - ``sudo apt-get install libssl-dev`` (best match for the already-installed libssl1.0.0)
      - ``sudo apt-get install libdb5.3-dev`` (matches the already-installed libdb5.3. This is a package to support the Oracle Berkeley DB)
      - ``sudo apt-get install libgdbm-dev`` (best match for the already-installed libgdbm3)

    - After these installations, Python ``make`` should only mention the following missing components, none of which are important (`Link 1 <https://gist.github.com/reorx/4067217>`__, `Link 2 <http://rajaseelan.com/2012/01/28/installing-python-2-dot-7-2-on-centos-5-dot-2/>`__):

      - bsddb185: Older version of Oracle Berkeley DB. Undocumented. Install version 4.8 instead.
      - dl: For 32-bit machines. Deprecated. Use ctypes instead.
      - imageop: For 32-bit machines. Deprecated. Use PIL instead.
      - sunaudiodev: For Sun hardware. Deprecated.
      - _tkinter: For tkinter graphy library, unnecessary if you don’t develop tkinter programs.

  - `Download <https://www.python.org/downloads/>`__ the ``.tgz`` for the desired version, extract it, and follow the build `instructions <https://docs.python.org/2/using/unix.html>`__.

    - ``wget https://www.python.org/ftp/python/2.7.12/Python-2.7.12.tgz`` (for example)
    - ``tar xzf Python-<version>.tgz``
    - ``cd Python-<version>``
    - ``./configure``
    - ``make``
    - ``sudo make altinstall``

      - If Ubuntu has a global Python 2.7.x installed, the result of ``make altinstall`` is that the original Python 2.7.x is still at ``/usr/bin/python2.7``, while the newly installed Python 2.7.x is at ``/usr/local/bin/python2.7``.

      - It seems to be a standard practice to put self-installed packages in ``/usr/local`` like this. `Link 1 <http://askubuntu.com/a/34922/>`__, `Link 2 <http://unix.stackexchange.com/a/11552/>`__

If you don't have ``pip``, get it with a wget of ``get-pip.py`` as linked in `pip’s docs <https://pip.pypa.io/en/latest/installing/>`__. Then run ``sudo /usr/local/bin/python2.7 get-pip.py``.

Check your pip's version with ``pip -V``. (The pip executable is in the same directory as the python one; make sure you refer to the python/pip you just installed). If pip says it's out of date, it'll suggest that you run a command to update it. Do that.
