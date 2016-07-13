Specific instructions for 2016 migration process
================================================


.. _y2016-migration-pgloader:

pgloader
--------


Notes about pgloader and our process
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
`pgloader <http://pgloader.io/index.html>`__ seems to be one of the best tools out there for porting a MySQL database to PostgreSQL. It takes a live database or file (e.g. CSV) as input, and outputs to a live PostgreSQL database. If we have live databases on both sides, then we don't even need to have a separate database dumping step, which should reduce the possible points of failure / data corruption.

At first the plan was to install pgloader on an AWS instance and connect to the UCSD CSE machine's MySQL database through the network. However, all attempts to the UCSD CSE machine's MySQL failed, even after disabling the ufw (firewall) configuration. Perhaps the UCSD CSE machine's router had a firewall which we didn't have control over. We briefly considered contacting CSE Help about it, but then decided not to give them another reminder about our very outdated server machine.

We ended up installing pgloader on the UCSD CSE machine, so that the MySQL connection would be local, and the PostgreSQL connection would be to the AWS instance (which has no firewall problems). We initially ruled out this idea because the UCSD CSE machine's Ubuntu is 11.04, a version that's no longer supported. However, it turned out to be possible.


Install pgloader on the UCSD CSE machine 
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
The machine's OS version, Ubuntu 11.04, stopped being supported in October 2012. Even if a pgloader build was possible to find for Ubuntu 11.04, it was likely to be very out of date, which would be a concern for porting correctness and being able to follow the online docs. So the preferred option was to build pgloader from source, using their `instructions <https://github.com/dimitri/pgloader/blob/master/INSTALL.md>`__ for doing so.

Here's what we get, in order:


freetds-common
..............
wget from `here <http://old-releases.ubuntu.com/ubuntu/pool/main/f/freetds/freetds-common_0.82-7_all.deb>`__, then ``sudo dpkg -i freetds-common_0.82-7_all.deb``.
  
  
libct4
......
This `requires <https://launchpad.net/ubuntu/natty/amd64/libct4/0.82-7>`__ ``freetds-common``.

wget from `here <http://launchpadlibrarian.net/49999586/libct4_0.82-7_amd64.deb>`__ then ``sudo dpkg -i libct4_0.82-7_amd64.deb``.

- This may get some messages like ``/usr/lib/x86_64-linux-gnu/libXt.so.6 is not a symbolic link``, but it doesn't necessarily mean the installation failed. Check with ``apt-cache policy libct4`` to see if it was installed.


libsybdb5
.........
This `requires <https://launchpad.net/ubuntu/natty/amd64/libsybdb5/0.82-7>`__ ``freetds-common``.

wget from `here <http://launchpadlibrarian.net/49999589/libsybdb5_0.82-7_amd64.deb>`__ then ``sudo dpkg -i libsybdb5_0.82-7_amd64.deb``. 

- This may get some messages like ``/usr/lib/x86_64-linux-gnu/libXt.so.6 is not a symbolic link``, but it doesn't necessarily mean the installation failed. Check with ``apt-cache policy libsybdb5`` to see if it was installed.


freetds-dev
...........
This requires ``libct4`` and ``libsybdb5``.

wget from `here <http://old-releases.ubuntu.com/ubuntu/pool/main/f/freetds/freetds-dev_0.82-7_amd64.deb>`__ then ``sudo dpkg -i freetds-dev_0.82-7_amd64.deb``. 
  
  
CCL (Clozure Common Lisp)
.........................
The installation for this is somewhat picky if we want to avoid errors when building pgloader. The best bet was to closely follow pgloader's `Dockerfile <https://github.com/dimitri/pgloader/blob/master/Dockerfile.ccl>`__ for CCL installation. As of 2015/05/18, that means running the following commands:

- ``cd /usr/local/src``
- ``svn co http://svn.clozure.com/publicsvn/openmcl/release/1.11/linuxx86/ccl``
- ``cp /usr/local/src/ccl/scripts/ccl64 /usr/local/bin/ccl``


pgloader
........
This requires Common Lisp (such as CCL) and ``freetds-dev``.

``git clone`` from the `pgloader repository <https://github.com/dimitri/pgloader>`__.

``cd`` into the cloned directory and then type ``make CL=ccl DYNSIZE=256``.

- One possible error when missing ``freetds-dev`` is: ``error opening shared object "libsybdb.so"`` (`Source <https://github.com/dimitri/pgloader/issues/131>`__)

- One possible error when the CCL installation is not correct is: ``[package buildapp]...........  > Error: Error #<SILENT-EXIT-ERROR #x302000F5869D>  > While executing: (:INTERNAL MAIN), in process listener(1).`` (`Related link <https://github.com/dimitri/pgloader/issues/392>`__)

- If errors occur, remember to ``make clean`` before trying another ``make``, just in case.

When ``make`` finishes successfully, the ``pgloader`` executable should be in ``<pgloader directory>/build/bin``.


(Old) pgloader installation with SBCL (Steel Bank Common Lisp)
..............................................................
As of 2016/05/18, SBCL is the default Common Lisp recommendation of pgloader (as opposed to CCL). But building pgloader with SBCL can result in a ``Heap exhausted`` error with lots of data, such as when porting just our ``reversion_version`` table. (`Related link <https://github.com/dimitri/pgloader/issues/327>`__)

Still, since we figured out how to build pgloader with SBCL, we might as well mention how we did it:

``wget`` SBCL as Linux/AMD64 from `this page <http://www.sbcl.org/platform-table.html>`__. We used SBCL 1.3.5.

Then, as instructed in the SBCL getting started page:

- Run ``bzip2 -cd sbcl-1.3.5-x86-64-linux-binary.tar.bz2 | tar xvf -``

- ``cd`` into the unpacked directory, then run ``sudo sh install.sh``.

  - The end output was: ``SBCL has been installed:  binary /usr/local/bin/sbcl  core and contribs in /usr/local/lib/sbcl/  Documentation:  man /usr/local/share/man/man1/sbcl.1``
  
Then in the pgloader directory, just run ``make``.


(Old) pgloader from binary on Windows
.....................................
This was initially used to test if pgloader seemed viable given our database structure.

Get an early 2015 pgloader binary `here <https://github.com/dimitri/pgloader/issues/159>`__, linked in the 4th comment. You'll also need sqlite3.dll from `here <https://www.sqlite.org/download.html>`__, plus libssl32.dll and libeay32.dll from `here <http://gnuwin32.sourceforge.net/packages/openssl.htm>`__; put those 3 .dll files in the same directory as the pgloader binary.

In the pgloader command run from command line, replace ``pgloader`` with whatever the pgloader executable name is.




Port the database using pgloader
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Create a load command file, say ``coralnet.load``, with the following contents:

::
    
  load database
   from mysql://<usernamehere>:<passwordhere>@localhost/coralnet
   into postgresql://<usernamehere>:<passwordhere>@<RDS-instance-public-address-goes-here>:5432/coralnet
    
   WITH quote identifiers, include drop
    
   SET maintenance_work_mem to '64MB', work_mem to '4MB'
    
   CAST type date to date using zero-dates-to-null
    
   EXCLUDING TABLE NAMES MATCHING ~/celery/;
   
Substitute the database users' usernames and passwords for ``<usernamehere>`` and ``<passwordhere>``. If you've been following the instructions here so far, the PostgreSQL username should be ``django``. Don't use the root/master user, because we need ``django`` to be the owner of the tables; this prevents permission errors later on when Django works with the database.

Also fill in ``<RDS-instance-public-address-goes-here>`` with the Public DNS of the RDS instance.

After the hostname is the database name; change that if it's something other than ``coralnet``.

Explanations on the rest of the command file:
   
- ``quote identifiers`` is needed so that upper/lower case of identifiers are maintained. This is important for some of our column names like ``annotatedByHuman``.
   
- ``include drop`` makes pgloader automatically drop the table named X in the target PostgreSQL database if the operation includes porting over table X. This allows us to conveniently retry the porting operation from scratch if something fails the first time.

  - Note that this drop will cascade to all objects referencing the target tables, possibly including tables that are not being ported over. However, if we're porting over the whole database at once, then it's not a problem.
   
- ``SET maintenance_work_mem to '64MB', work_mem to '4MB'`` sets PostgreSQL parameters on the amount of memory to use during certain operations. See the PostgreSQL docs for `work_mem <http://www.postgresql.org/docs/current/static/runtime-config-resource.html#GUC-WORK-MEM>`__ and `maintenance_work_mem <http://www.postgresql.org/docs/current/static/runtime-config-resource.html#GUC-MAINTENANCE-WORK-MEM>`__. These can affect whether 
   
- ``CAST type date to date using zero-dates-to-null`` is a casting rule which says to cast MySQL ``date`` types to PostgreSQL ``date`` types, using pgloader's transformation function which converts any ``0000-00-00`` dates to ``NULL``.

  - pgloader uses this transformation function by default only if the MySQL column's default value is ``0000-00-00``. Our ``images_metadata`` table's ``photo_date`` column doesn't have a default value because it accepts NULL values. However, we do have a few ``photo_date`` values which are ``0000-00-00``, perhaps because the column used to be non-NULL. Therefore, we DO have zero dates to convert, yet our column doesn't match pgloader's default rules for converting zero dates, so we define our own rule.
  
  - Defaulting to ``0000-00-00`` is standard MySQL behavior: `Link <http://dev.mysql.com/doc/refman/5.5/en/datetime.html>`__, `Another link (possibly on old MySQL versions) <http://sql-info.de/mysql/gotchas.html#1_14>`__
   
- ``EXCLUDING TABLE NAMES MATCHING ~/celery/`` excludes tables whose names match the regular expression ``celery``. This should exclude all the ``celery_<name>`` and ``djcelery_<name>`` tables; we don't need these tables any longer, and at least one of them is quite large. Note that the `pgloader docs <http://pgloader.io/howto/pgloader.1.html>`__ have a section on regular expression syntax.

- The newlines and amount of whitespace shouldn't matter. There must be a semicolon after the last command.

- See the `pgloader docs <http://pgloader.io/howto/pgloader.1.html>`__ for more details.

Run pgloader: ``<pgloader directory>/build/bin/pgloader coralnet.load``

For us, this process takes about 45 minutes. Confirm that there are no errors.

Two possible warnings that should be acceptable are:

- ``Postgres warning: table "..." does not exist, skipping``. See `this link <http://pgloader.io/howto/sqlite.html>`__: "the WARNING messages we see here are expected as the PostgreSQL database is empty when running the command, and pgloader is using the SQL commands DROP TABLE IF EXISTS when the given command uses the include drop option."

- ``identifier "idx_20322_guardian_groupobjectpermission_object_pk_122874e9_uniq" will be truncated to "idx_20322_guardian_groupobjectpermission_object_pk_122874e9_uni"``. To our knowledge at least, there's nothing that would break if an index were renamed.

At this point, it's a good idea to make a snapshot of the RDS instance, in case we make a mistake on the Django migration steps. You can create a snapshot from Amazon's RDS Dashboard.


.. _y2016-migration-django-migrations:

Django migrations
-----------------
These are the migrations that the UCSD CSE production DB must run to get completely up to date with the latest Django and repo code.

The migration numbers are in Django's new migration framework unless specifically denoted as South migrations. (Last update: Django 1.9.5)

Run these in order:

- contenttypes: fake 0001, run 0002
- auth: fake 0001, run 0002-0007
- admin: fake 0001, run 0002
- sessions: fake 0001
- sites: fake 0001, run 0002
- userena: fake 0001
- umessages: fake 0001
- guardian: fake 0001
- easy_thumbnails: fake 0001, run 0002 (OR run South's 0016, then fake new 0001-0002)
- accounts: fake 0001-0002, run the rest
- images: fake 0001, run the rest
- annotations: fake 0001-0003, run the rest
- bug_reporting: fake 0001, run the rest
- errorlogs: run 0001 (since this is a new app)
- reversion: run South's 0006-0008, then fake new 0001, then run new 0002 (see notes below)


contenttypes
~~~~~~~~~~~~
Do these migrations first. If you don't run the ``contenttypes`` migrations early enough, you may get ``RuntimeError: Error creating new content types. Please make sure contenttypes is migrated before trying to migrate apps individually.`` `Link 1 <http://stackoverflow.com/questions/29917442/error-creating-new-content-types-please-make-sure-contenttypes-is-migrated-befo>`__, `Link 2 <https://code.djangoproject.com/ticket/25100>`__

You might get message(s) like ``The following content types are stale and need to be deleted``. You should be safe to answer yes to the "Are you sure?" prompt(s). See `this link <http://stackoverflow.com/questions/16705249/stale-content-types-while-syncdb-in-django>`__. We don't define any foreign keys to ``ContentType``.

In our case, we have the stale contenttypes ``auth | message`` and ``annotations | annotation_attempt``. Each takes about 2 minutes to delete.


reversion
~~~~~~~~~
``reversion`` is tricky. Before our 2016 upgrading process, we had reversion 1.5.1, and that had South migrations numbered up to 0005. But just before reversion switched to the new migrations, they had made South migrations up to 0008. Then they merged the South migrations 0001-0008 into a new 0001 to make things cleaner.

To apply the ``reversion`` migrations:

- pip-install ``Django==1.6``, ``django-reversion==1.8.4``, and ``South``.
- Add ``'south'`` to your ``INSTALLED_APPS`` setting.
- Comment out all other apps in ``INSTALLED_APPS`` except for Django core apps, south, and reversion. This is probably the simplest way to avoid South errors about other apps having `ghost migrations <http://stackoverflow.com/questions/8875459/what-is-a-django-south-ghostmigrations-exception-and-how-do-you-debug-it>`__.
- Change the ``DATABASES`` setting's engine to ``'postgresql_psycopg2'`` to make Django 1.6 happy. (This is the same engine, just under a different name.)
- Use ``manage.py migrate --list`` to confirm that ``reversion`` has run migrations 0001 to 0005.
- Use ``manage.py migrate reversion`` to run migrations 0006 to 0008.
- Revert the ``INSTALLED_APPS`` and ``DATABASES`` settings. Assuming you made these changes in ``base.py``, just do ``git checkout config/settings/base.py``.
- pip-install the latest ``Django`` and ``django-reversion`` again, and uninstall ``South``.
- Now you can see with ``manage.py showmigrations`` that the ``reversion`` migration numbers have changed. Fake-run 0001, then run 0002.

At this point, it's a good idea to make another snapshot of the RDS instance.


File transfer to AWS S3
-----------------------

SSH into an EC2 instance. Mount the CoralNet alpha server's filesystem using SSHFS.

- ``sudo apt-get install sshfs``
- ``sudo mkdir /mnt/cnalpha``
- ``sudo sshfs <username>@<alpha server host>/ /mnt/cnalpha`` to mount the root of the alpha server's filesystem at ``/mnt/cnalpha``.

Install and configure the AWS command line interface.

- ``sudo apt-get install awscli``
- ``aws configure`` - When prompted, be sure to specify an access key that has access to the desired S3 bucket.

You can sync small directories with the ``aws s3 sync`` command. For example: ``sudo aws s3 sync /mnt/cnalpha/path/to/media/label_thumbnails s3://<bucket-name>/media/labels``

Unfortunately, the ``aws s3 sync`` command seems to hang without transferring anything when it comes to large directories. (`Related GitHub issue <https://github.com/aws/aws-cli/issues/1775>`__)
Instead, use the ``scripts/s3_sync.py`` script in our repository to transfer the files. For example: ``sudo python path/to/s3_sync.py /mnt/cnalpha/path/to/media/data/original s3://<bucket-name>/media/images``. This script basically loops over the files and copies them one by one using ``aws s3 cp``.

The script has a ``--filter`` option that allows you to try transferring just a subset of images. For example, to transfer all files whose filenames start with ``00``, run: ``sudo python path/to/s3_sync.py <src> <dest> --filter "00.*"``

The process can be run in the background, and should not be interrupted even if you close your SSH session (despite SSHFS being used). When finished, a summary .txt file should be written, so you can see the number of files copied, time elapsed, etc. For us, the transfer of 1.2 TB of 600k image files would take about 15.5 days.