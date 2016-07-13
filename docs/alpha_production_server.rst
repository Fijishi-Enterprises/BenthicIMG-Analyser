Alpha production server
=======================
This page contains miscellanous notes about the old alpha production server - a physical server machine running Linux.


Hardware
--------
- Motherboard: ASUS M4A78LT-M (2011/07)
- System disk: 1 TB, WD Blue, WD10FZEX (2016/06)
- Data disks: 2x 4 TB, Seagate (2014/10)

  - We only use one 2 TB partition on each disk. There was some difficulty with creating partitions larger than 2.2 TB; it's probably doable but we just never took the trouble to figure it out.
  
- Memory: 4x 4 GB DDR3 1333Mhz, G.SKILL (2011/07)
- Processor: AMD Phenom II X4 945 6MB L3 Cache (2011/07)
- Case: Cooler Master Elite 335 RC-335-KKN1-GP, Black (2011/07)

The disk drive bays' purple locks haven't stood the test of time. Be careful with them as they'll break easily. Get the disk well aligned in the bay first, then insert the lock all the way in before turning it (the lock has little words and arrows showing what the lock/unlock directions are). The disks seem to stay reasonably secure even without the locks, but it's best to use the locks if possible.

To enter the BIOS at startup, press and hold Delete on the screen with the motherboard name. (`Source <http://www.manualslib.com/products/Asus-M4a78lt-M-778986.html>`__) You might have to wait at least a half second after the screen's appearance before starting to hold Delete.


RAID setup (on clean data disks)
--------------------------------
This section goes over installing a RAID 1 configuration on two data disks (not system disks) which are okay to be formatted in the process. The RAID configuration will be OS-controlled (rather than BIOS or motherboard-controlled), and created using ``mdadm``. Our primary resource was `this mysolutions.it guide <http://www.mysolutions.it/tutorial-mdadm-software-raid-ubuntu-debian-systems/#create-mdadm-raid>`__.

``sudo install mdadm``

``lsblk`` to confirm the disks, their partitions, and their mount statuses.

Format the disk partitions in the ext4 filesystem: Assuming the disk partitions of interest are ``sdb1`` and ``sdc1``, run ``sudo mkfs.ext4 /dev/sdb1`` and ``sudo mkfs.ext4 /dev/sdc1``.

- During the 2016/06 recovery, each 2 TB partition took less than a minute to format.

Run ``sudo mdadm -Q --examine /dev/sdb1`` and ``sudo mdadm -Q --examine /dev/sdc1`` to ensure that the partitions don't have any remaining RAID status from a former configuration. You should get a result like ``mdadm: No md superblock detected on /dev/sdb1``.

Sanity check the disks: use ``sudo umount /dev/sd<letter>1`` to unmount their partitions, then ``sudo fsck /dev/sd<letter>1``.

Create the RAID 1 array: ``sudo mdadm --create --verbose /dev/md0 --level=1 --raid-devices=2 /dev/sdb1 /dev/sdc1`` (Assuming the partitions you want are ``sdb1`` and ``sdc1``.)

- You can check the progress using ``cat /proc/mdstat``, or get an auto-updating display with ``watch cat /proc/mdstat`` (which can be exited safely with Ctrl-C). (`Source <http://superuser.com/questions/820547/why-raid1-is-resynching-so-long>`__) During the 2016/06 recovery, for our 2 TB partitions, this took about 4 hours.

Check the RAID status: ``sudo mdadm --detail /dev/md0``. There should be 2 active and working devices, and the state should be clean.

- The mysolutions.it guide says you'd need to run ``sudo mdadm --assemble /dev/md0 /dev/sdb1 /dev/sdc1`` first, but this seemed to not be necessary during the 2016/06 recovery - the command just got a message ``mdadm: /dev/sdb1 is busy - skipping``.

Format the RAID device: ``sudo mkfs.ext4 /dev/md0`` (Assuming the device is ``md0``)

Auto-mount the mdadm RAID on startup.

- Decide what your mount point will be and ``mkdir`` it.

  - Note that putting mount points as subdirectories of ``/mnt`` is standard, and that you can readily make symbolic links to mount points.
  
- Manually edit ``/etc/fstab`` according to steps 7 and 8 of `the mysolutions.it guide <http://www.mysolutions.it/tutorial-mdadm-software-raid-ubuntu-debian-systems/#create-mdadm-raid>`__.

  - During the 2016/06 recovery, the fields after the mount point were ``ext4``, ``defaults``, ``0``, and ``2``.
  
    - Explanation on the second number: "The sixth field, (fs_passno), is used by the fsck(8) program to determine the order in which filesystem checks are done at reboot time. The root filesystem should be specified with a fs_passno of 1, and other filesystems should have a fs_passno of 2. ... If the sixth field is not present or zero, a value of zero is returned and fsck will assume that the filesystem does not need to be checked." (`Source <http://askubuntu.com/questions/9939/what-does-the-last-two-fields-in-fstab-mean>`__)
    
- Test the auto-mount: ``sudo mount -a``, then check if the mount succeeded using ``lsblk``.

- Test the auto-mount with a reboot. The RAID device number may change (e.g. to ``md127``, but that should be fine.

You can start copying data (e.g. with ``rsync``) to the RAID mount point now.


Linux
-----
Ubuntu Server 14.04 (installed 2016/06).

- In 2011/07 we started off by using a standard GUI version of Ubuntu.
- Around 2014/10 we switched to Ubuntu Server 11.04 (command line only) since the xserver of the previous install started having problems.

Details during Ubuntu Server 14.04 installation via USB thumb drive:

- "Your installation CD-ROM couldn't be mounted. Try again to mount the CD-ROM? (Yes/No)"

  - When you get the error, Alt-F2 to a second console.
  - Find out which device your USB thumb drive is. (e.g. ``df``, or ``tail -n 100 /var/log/syslog``)
  - Mount that device to ``/cdrom``. (e.g. ``mount /dev/sd<letter>1 /cdrom``)
  - Alt-F1 to get back to the install console, then select No to the retry. Then select the CD-ROM detection step from the main menu.
  
- On the partitioning step, "Guided - use entire disk" on the system disk should be fine.


Network
-------
During the 2016/06 recovery, we skipped the automatic network configuration step during Ubuntu installation.

Following `this link <https://swiftstack.com/docs/install/configure_networking.html#changing-network-configuration>`__ for the most part, edit ``/etc/network/interfaces`` and add lines for the ``address``, ``netmask``, ``gateway``, and ``dns-nameservers`` of your network interface.

Then restart the network interface: if it's called ``eth0``, then run ``ifdown eth0`` and ``ifup eth0``.

Use ``ifconfig -a`` to confirm the configuration.

Possible troubleshooting steps:

- ``ping <the machine's IP>``
- ``ping <the gateway>``
- ``ping google.com``
- ``wget http://ipinfo.io/ip -qO -`` to confirm the public IP (`Source <http://askubuntu.com/questions/95910/command-for-determining-my-public-ip>`__)


Firewall
--------
In the absence of AWS security groups, we need to configure our own firewall. Linux has iptables, and Ubuntu has ``ufw`` which provides a slightly easier interface for iptables. See `this link <https://help.ubuntu.com/community/UFW>`__ for details on ``ufw``.

By default, ``ufw`` allows all outgoing traffic and denies all incoming traffic. We will want to allow the following incoming traffic:

- HTTP from any IP: ``sudo ufw allow 80``
- HTTPS from any IP: ``sudo ufw allow 443``
- SSH/FTP from system admins' IPs: ``sudo ufw allow from 11.22.33.44 to any port 22``

System admins should check if their IPs are static or dynamic. If dynamic, workarounds (with slight security tradeoffs) include allowing their whole range of possible IPs, or allowing the static IP of another machine which they can SSH into.

Once things are configured, use ``sudo ufw enable`` to get the firewall running. Other commands are ``sudo ufw status`` and ``sudo ufw disable``.

Notes:

- To check the firewall allow/deny rules, ensure the firewall is enabled and then ``sudo ufw status``. There isn't a particularly easy way to check the rules when the firewall's disabled.

- Example of deleting a rule, if needed: ``sudo ufw delete allow from 11.22.33.44 to any port 22``

- When you update the firewall rules, the update's effects on existing SSH connections are immediately applied, so watch out. 


SSH
-----
Ensure an SSH server is installed: ``sudo openssh-server``

``sudo vim /etc/ssh/sshd_config`` and append the following lines if similar ones aren't present already (`Source <http://askubuntu.com/questions/16650/create-a-new-ssh-user-on-ubuntu-server>`__):

- ``Port 22``
- ``PermitRootLogin no`` (maybe not necessary, but we shouldn't need to log in as root)
- ``AllowUsers user1 user2`` (where user1, user2 are the Ubuntu users who are allowed to SSH in)

  - There is also a stricter syntax: ``AllowUsers user1@11.22.33.44 user2@55.66.77.88``. However, this is mostly redundant if ``ufw`` already has IP-specific rules and everyone on the system is an admin. 

Then ``sudo service ssh reload``.


Git
-----
Note that Git tracks changes of Linux file permissions.

After doing the 2016/06 restore, we had the repo files in place before even installing git, and ended up changing the permissions of some of those files while setting things up. Then ``git status`` showed a lot of unstaged changes. This took us by surprise, but we managed to get out of the mess by carefully using ``diff`` to check which files had a permissions mode change as the only change, and reverting those files.


MySQL
-----
As of the 2016/06 recovery, we use 5.5.49-0ubuntu0.14.04.1, and all of our tables are (unfortunately) MyISAM.

Setup:

``sudo apt-get install mysql-server-5.5``, then set a MySQL administrative "root" user as the GUI prompts you to do.

- When we installed this during the 2016/06 recovery, the network was down so we hunted for all the package dependencies manually starting from `this link <http://packages.ubuntu.com/trusty/mysql-server-5.5>`__, and copied them from a laptop via thumb drive. The packages obtained were:

  - mysql-common
  - libdbi-perl
  - libmysqlclient18
  - libdbd-mysql-perl
  - libterm-readkey-perl
  - mysql-client-core-5.5
  - mysql-client-5.5
  - libaio1
  - mysql-server-core-5.5
  - mysql-server-5.5
  
Log into MySQL: ``mysql -u root -p`` and type the root password.

Create a ``django`` user: ``CREATE USER 'django'@'localhost' IDENTIFIED BY 'cleartextpassword';`` (`Source <https://dev.mysql.com/doc/refman/5.5/en/create-user.html>`__)

- This command, including the password, will be logged in MySQL's logs. Unfortunately, there seems to be no way around this in MySQL 5.5, so the logs should be purged afterward.

Allow the ``django`` user full access to the (future) ``coralnet`` and ``coralnet_test`` databases: ``GRANT ALL PRIVILEGES ON `coralnet`.* TO 'django'@'localhost';``, ``GRANT ALL PRIVILEGES ON `test_coralnet`.* TO 'django'@'localhost';``

Log out of MySQL. Log back in as ``django``: ``mysql -u django -p``

Create the ``coralnet`` database: ``create database coralnet;``


Restoring data
..............
Load our existing data into this database: ``use coralnet;``, then ``source /path/to/backup.sql``. During the 2016/06 recovery, this took about 28 minutes to finish.

Check that the data is there: ``show tables;``, ``SELECT count(*) FROM <table_name>;``, etc.


Automatic database backups
..........................
Mostly following instructions from `this blog post <https://www.rosehosting.com/blog/how-to-install-and-configure-automysqlbackup/>`__.

Get automysqlbackup: ``wget http://downloads.sourceforge.net/project/automysqlbackup/AutoMySQLBackup/AutoMySQLBackup%20VER%203.0/automysqlbackup-v3.0_rc6.tar.gz``.

``tar zxvf`` the download, then run the ``./install.sh``. When prompted for directories, choosing defaults should be fine.

Open the config file: ``vim /etc/automysqlbackup/automysqlbackup.conf``. Uncomment and edit the following lines (if a config variable value is not listed, then read the config file comments and enter an appropriate value depending on your setup):

::

  CONFIG_mysql_dump_username
  CONFIG_mysql_dump_password
  CONFIG_mysql_dump_host
  CONFIG_backup_dir='/var/backups/db'
  CONFIG_db_names=( 'coralnet' )
  CONFIG_do_monthly
  CONFIG_do_weekly
  CONFIG_rotation_daily
  CONFIG_rotation_weekly
  CONFIG_rotation_monthly
  CONFIG_mysql_dump_port=3306
  CONFIG_mysql_dump_single_transaction='no'
  CONFIG_mysql_dump_compression='gzip'
  
- The default backup dir is ``'/var/backup/db'``, but Ubuntu already seems to have ``/var/backups`` by default, so we might as well use that.
  
- 3306 is the default port for MySQL. MySQL should already be using this port if we didn't configure it otherwise. Using the default port shouldn't a security issue if ``ufw`` doesn't allow public port 3306 traffic.
  
- Single-transaction must be no, because we have MyISAM tables. This means that backups could be inconsistent, but the alternative is to read-lock the tables during backup, which is bad for site availability.

You can invoke the backup manually as a test: ``sudo automysqlbackup``

Check ``/etc/cron.daily`` to ensure it contains an ``automysqlbackup`` executable.

Open the root-cronjob file: ``sudo crontab -e``. Add a line with the command ``automysqlbackup``. Example of running at 4 AM every day: ``0 4 * * * automysqlbackup``

Now you should be good to go; the backups should run daily, and during that daily run, the weekly/monthly config rules should be respected as well.


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


Other gritty details on server setup
------------------------------------
- The Python install we're using is in ``/usr/local/bin`` and ``/usr/local/lib``.
- The non-symlink cnhome directory must be named ``CoralNet`` to satisfy bad imports like ``CoralNet.exceptions``. (These imports exist because we have stuff like ``exceptions.py`` at the root of our project.)


How to stop the vision backend for server updates
-------------------------------------------------
Look in the ``/cnhome/logs`` directory.

if the file ``nrs_running_flag`` is present, then the backend is running.

Put a file ``break_flag`` in that same directory. This means that the backend will break as soon as it has finished the current job, and not re-start until that flag is removed.

Wait until ``nrs_running_flag`` disappears, and then you are good to go. Double check by running ``top`` also, to see if no Matlab stuff is running.

Once you're done updating the server, remember to remove ``break_flag``.

The relevant code is in ``images/tasks.py``, ``nrs_main_wrapper()``.
