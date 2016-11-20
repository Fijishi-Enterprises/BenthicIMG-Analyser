.. _server_instances:

Server instances
================


EC2 Linux instance setup
------------------------
- *Production/staging server*


Creating an EC2 instance
~~~~~~~~~~~~~~~~~~~~~~~~

First ensure you've :ref:`created a key pair <aws_key_pair>` to authenticate with EC2 instances.

Ensure you've created a Security Group which allows:

- Inbound SSH connections (port 22) from the machine you are working from. (Use a site like `whatismyip.com <https://www.whatismyip.com/>`__ to find your IP.)
- Inbound HTTP (port 80) and HTTPS (port 443) connections from all IPs.

Use the EC2 console to create a new EC2 instance.

- For a production server:

  - Pick t2.large as the instance type.

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

  - Associate an Elastic IP with the instance.

    - Create an Elastic IP (also in the EC2 console) if you don't have one.

    - Select your Elastic IP, then Actions -> Associate Address. Select your new EC2 instance.

- For a staging server:

  - Pick t2.medium as the instance type.

  - On the "Configure Instance Details" step:

    - (TODO: Consider whether Spot Instances would be acceptable here.)

    - Select an IAM role. This way the EC2 instance gets associated with an IAM role, and the instance's ``secrets.json`` file doesn't have to specify AWS credentials.

  - On the "Configure Security Group" step, choose the previously mentioned Security Group.

  - Launch the instance. Upon clicking "Launch", associate a key pair that you have control over. This key pair will be used to authenticate with the default user (e.g. the ``ubuntu`` user for an Ubuntu Linux instance).

On the list of instances, give your new instance a descriptive name.

Edit the RDS instance's Security Group to allow inbound connections from the EC2 instance's Security Group. (This allows Django to connect to the database.) In the Source box, type ``sg`` and the security group choices should appear.

SSH into the EC2 instance using the key pair.

- Check the instance on the EC2 dashboard, and find its Public DNS. Use that as the host name to SSH into.
- Log in with the EC2 instance's default username. The username varies depending on which Linux you're using (it's ``ubuntu`` for Ubuntu instances): `Link <http://docs.aws.amazon.com/AWSEC2/latest/UserGuide/TroubleshootingInstancesConnecting.html#TroubleshootingInstancesConnectingPuTTY>`__


Instance type reasoning
.......................
For our choice of t2.large, our general goal is long-term funding survival. We should only get a more powerful instance if the current instance has poor performance in many parts of the site. If poor performance is limited to a few views, we should do our best to optimize those pages or make tradeoffs, such as caching page computations.


.. _aws_cli_install:

Set up the AWS command line interface (CLI)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Install the AWS CLI: ``sudo apt-get install awscli``

Run ``aws configure``. You'll be prompted for the following:

- Just hit Enter on the Access Key ID and Secret Access Key prompts, since the instance is already associated with an IAM Role.
- For Default region name, enter our primary region, such as ``us-west-2``.
- Just hit Enter on the Default output format. This determines the formatting style for command output, but the default seems to work fine.


Add users to the EC2 instance
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
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


More instance setup
~~~~~~~~~~~~~~~~~~~
- *Production/staging server*

Upgrade system packages: ``sudo apt-get update`` then ``sudo apt-get upgrade`` on Ubuntu. Log out. Go to the EC2 dashboard and reboot the EC2 instance. Log in again.

  - Although it's not all that important in this case: "We recommend that you use Amazon EC2 to reboot your instance instead of running the operating system reboot command from your instance. If you use Amazon EC2 to reboot your instance, we perform a hard reboot if the instance does not cleanly shut down within four minutes. If you use AWS CloudTrail, then using Amazon EC2 to reboot your instance also creates an API record of when your instance was rebooted." (`Link <http://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-instance-reboot.html>`__)

Create a ``/srv/www`` directory for putting website files. (This seems to be a recommended, standard location: `Link 1 <http://serverfault.com/questions/102569/should-websites-live-in-var-or-usr-according-to-recommended-usage>`__, `Link 2 <http://superuser.com/questions/635289/what-is-the-recommended-directory-to-store-website-content>`__)

- Change the directory's group to ``www-data``: ``sudo chgrp www-data www``
- Add your user to the ``www-data`` group: ``sudo usermod -aG www-data <username>``
- Check that you did it right: ``cat /etc/group``
- If you are currently signed in as that user, logout and login to make the new permissions take effect. (`Source <http://unix.stackexchange.com/questions/96343/how-to-take-effect-usermod-command-without-logout-and-login>`__)
- Allow group write permissions: ``sudo chmod g+w www``
- Make all new files created in the ``www`` directory have their group set to the directory's group: ``sudo chmod g+s www``

When you do the Git setup step, put the project files in ``/srv/www``, such that the directory ``/srv/www/coralnet`` is the Git repository root.


Upgrading Linux packages on an EC2 instance
-------------------------------------------
When you log into Ubuntu, it should say how many updates are available. If there are one or more updates, run ``sudo apt-get update`` then ``sudo apt-get upgrade``.


Upgrading Linux kernel on an EC2 instance
-----------------------------------------
When you log into Ubuntu, it might say "System restart required". This is probably because some of the updates are part of the kernel (`Link <http://superuser.com/questions/498174/>`__).

There are non-trivial ways of applying even these updates without restarting. One way is to use Oracle's `ksplice <http://www.ksplice.com/>`__, but this software isn't free for Ubuntu Server.

If a restart is acceptable, here's a simple update procedure:

- Log into the EC2 instance. Put up the maintenance message and wait for the maintenance time.

- Stop gunicorn. ``sudo apt-get update`` then ``sudo apt-get upgrade`` (assuming Ubuntu). Log out. Go to the EC2 dashboard and reboot the EC2 instance. Wait for the reboot to finish.

- Log in again. Start redis, nginx (if not auto-starting), and gunicorn. Take down the maintenance message.


Upgrading Linux version of the EC2 instance
-------------------------------------------
Probably the most doubt-free way to do this is to create a new EC2 instance with that new Linux version, and migrate the server to that EC2 instance. This can be a relatively quick process if you have a Docker file specifying how to set up a new instance.

However, if you want to try upgrading the Linux version on an instance, it should be possible. In this case it should say "you can run ``do-release-upgrade`` to upgrade".

It'll advise you that the restart of certain services could interrupt your SSH session, and that this can be mitigated by opening access to port 1022. Go ahead and do that in the EC2 instance's security group.


Reserving an EC2 instance
-------------------------
- *Production server - ONLY if we are sure about sticking with a particular EC2 instance type for 1-3 years*

Typically you are charged a certain rate for running an EC2 instance, and you're simply charged based on how long you run that instance.

There is also the option to reserve an EC2 instance. When you reserve an instance, you pay an upfront fee and get a lower cost rate. After the reservation term is over, this should result in less cost compared to not reserving the instance. Cost savings depend on the reservation type (no upfront, partial upfront, or all upfront), and range from roughly 30%-40% compared to no reservation.

In return, you must pay the rate until the end of the term, even if you stop using the instance before then.

Amazon gives this incentive to reserve instances because it gives them more information about what resources they need to give you in the long term.

A reservation's instance type (e.g. t2.medium) and availability zone (e.g. uswest2) are fixed, but the reservation can be applied to different instances throughout the reservation's lifetime.

`Link 1 <https://www.quora.com/What-is-the-concept-behind-reserved-instances-for-EC2>`__, `Link 2 <https://alestic.com/2014/12/ec2-reserved-instances/>`__, `Link 3 <https://skeddly.desk.com/customer/portal/articles/1348371-how-reserved-ec2-instances-work>`__
