.. _server_instances:

Server instances
================


EC2 Linux instance creation
---------------------------
- *Production/staging server*

Go to the Amazon EC2 dashboard. Create a Security Group which allows:

- Inbound SSH connections (port 22) from the machine you are working from. (Use a site like `whatismyip.com <https://www.whatismyip.com/>`__ to find your IP.)
- Inbound HTTP and HTTPS connections from all IPs.

Use the dashboard to create a new EC2 instance.

- Pick t2.large for a production server, t2.medium for a staging server.
- On the "Configure Instance Details" step, check "Protect against accidental termination".
- On the "Add Storage" step, uncheck "Delete on Termination".

Edit the RDS instance's Security Group to allow inbound connections from the EC2 instance's Security Group. (This allows Django to connect to the database.) In the Source box, type ``sg`` and the security group choices should appear.

Create a key pair for your IAM user if you haven't already, and SSH into the EC2 instance using the key pair.

- See `this Amazon docs page <http://docs.aws.amazon.com/AWSEC2/latest/UserGuide/get-set-up-for-amazon-ec2.html#create-a-key-pair>`__ for details on creating and configuring the key pair.
- Check the instance on the EC2 dashboard, and find its Public DNS. Use that as the host name to SSH into.
- Log in with the EC2 instance's default username. The username varies depending on which Linux you're using (it's ``ubuntu`` for Ubuntu instances): `Link <http://docs.aws.amazon.com/AWSEC2/latest/UserGuide/TroubleshootingInstancesConnecting.html#TroubleshootingInstancesConnectingPuTTY>`__


Instance type reasoning
.......................
Our general goal is long-term funding survival. We should only get a more powerful instance if the current instance has poor performance in many parts of the site. If poor performance is limited to a few views, we should do our best to optimize those pages or make tradeoffs, such as caching page computations.


EC2 Linux instance setup
------------------------
- *Production/staging server*

Create a user for each person, using ``sudo adduser <username> --disabled-password`` and then following the rest of the instructions in `this Amazon guide <http://docs.aws.amazon.com/AWSEC2/latest/UserGuide/managing-users.html>`__.

- The guide explains that it's insecure to share the default user (``ubuntu`` in this case) between multiple people, because "that account can cause a lot of damage to a system when used improperly."

For each of those users, allow them to use ``sudo`` without specifying a password (since requiring a private key login makes a password redundant):

- Add the user to the sudoers group: ``sudo usermod -a -G sudo <username>``
- Run ``sudo visudo -f /etc/sudoers.d/mysudoers`` to edit a new sudoers file called ``mysudoers``. Add the line: ``<username> ALL=NOPASSWD: ALL`` (`Source <http://superuser.com/a/869145/>`__)

  - If you are adding multiple users, just use the same sudoers file for both users.
  - FYI, the default ``ubuntu`` user doesn't require a sudo password by default. That's configured in ``/etc/sudoers.d/90-cloud-init-users``. (`Source <http://askubuntu.com/questions/309418/make-an-amazon-ec2-instance-ask-for-sudoing-password>`__) This is because the ``ubuntu`` user doesn't have a login password by default, since as previously mentioned, a private key requirement makes a password redundant.

Once you're in the SSH session, upgrade system packages: ``sudo apt-get update`` then ``sudo apt-get upgrade`` on Ubuntu. Log out. Go to the EC2 dashboard and reboot the EC2 instance. Log in again.

Create a ``/srv/www`` directory for putting website files. (This seems to be a recommended, standard location: `Link 1 <http://serverfault.com/questions/102569/should-websites-live-in-var-or-usr-according-to-recommended-usage>`__, `Link 2 <http://superuser.com/questions/635289/what-is-the-recommended-directory-to-store-website-content>`__)

- Change the directory's group to ``www-data``: ``sudo chgrp www-data www``
- Add your user to the ``www-data`` group: ``sudo usermod -aG www-data usernamegoeshere``
- Check that you did it right: ``cat /etc/group``
- If you are currently signed in as that user, logout and login to make the new permissions take effect. (`Source <http://unix.stackexchange.com/questions/96343/how-to-take-effect-usermod-command-without-logout-and-login>`__)
- Allow group write permissions: ``sudo chmod g+w www``
- Make all new files created in the ``www`` directory have their group set to the directory's group: ``sudo chmod g+s www``

When you do the Git setup step, put the project files in ``/srv/www``, such that the directory ``/srv/www/coralnet`` is the Git repository root.


Updating Linux packages on an EC2 instance
------------------------------------------
TODO


Updating Linux version of an EC2 instance
-----------------------------------------
TODO


Reserving an EC2 instance
-------------------------
- *Production server - ONLY if we are sure about sticking with a particular EC2 instance type for 1-3 years*

Typically you are charged a certain rate for running an EC2 instance, and you're simply charged based on how long you run that instance.

There is also the option to reserve an EC2 instance. When you reserve an instance, you pay an upfront fee and get a lower cost rate. After the reservation term is over, this should result in less cost compared to not reserving the instance. Cost savings depend on the reservation type (no upfront, partial upfront, or all upfront), and range from roughly 30%-40% compared to no reservation.

In return, you must pay the rate until the end of the term, even if you stop using the instance before then.

Amazon gives this incentive to reserve instances because it gives them more information about what resources they need to give you in the long term.

A reservation's instance type (e.g. t2.medium) and availability zone (e.g. uswest2) are fixed, but the reservation can be applied to different instances throughout the reservation's lifetime.

`Link 1 <https://www.quora.com/What-is-the-concept-behind-reserved-instances-for-EC2>`__, `Link 2 <https://alestic.com/2014/12/ec2-reserved-instances/>`__, `Link 3 <https://skeddly.desk.com/customer/portal/articles/1348371-how-reserved-ec2-instances-work>`__
