.. _beta_migration_database:

Database migration from alpha to beta
=====================================


.. _beta-migration-pgloader:

pgloader
--------


Notes about pgloader and our process
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
`pgloader <http://pgloader.io/index.html>`__ is a popular tool for porting a MySQL database to PostgreSQL. It takes a live database or file (e.g. CSV) as input, and outputs to a live PostgreSQL database. If we have live databases on both sides, then we don't even need to have a separate database dumping step, which should reduce the possible points of failure / data corruption.

Our use case is to install pgloader on the alpha server, and run pgloader to transfer the data directly from the alpha server's MySQL to the beta RDS instance's PostgreSQL without any intermediate files.

At first the plan was to install pgloader on an AWS instance and connect to the alpha server's MySQL database through the network. However, all attempts to connect to the alpha server's MySQL failed, even after disabling the ufw (firewall) configuration. Perhaps the alpha server's router had a firewall which we didn't have control over. We briefly considered contacting CSE Help about it, but then decided not to give them another reminder about our very outdated server machine.

We ended up installing pgloader on the alpha server, so that the MySQL connection would be local, and the PostgreSQL connection would be to the AWS instance (which has no firewall problems). We initially ruled out this idea because the alpha server's Ubuntu is 11.04, a version that's no longer supported by the Ubuntu OS's publisher. However, it turned out to be possible. This was all figured out around 2016.05.

Later, the alpha server ended up on Ubuntu 14.04 after the 2016.06 server recovery. So we also ended up figuring out how to build and run pgloader in that case.



Installing Common Lisp
~~~~~~~~~~~~~~~~~~~~~~
Building pgloader from source requires Common Lisp. SBCL and CCL are known to work with pgloader.


CCL (Clozure Common Lisp)
.........................
The installation for this is somewhat picky if we want to avoid errors when building pgloader. The best bet was to closely follow pgloader's `Dockerfile <https://github.com/dimitri/pgloader/blob/master/Dockerfile.ccl>`__ for CCL installation. As of 2016/05/18, that means running the following commands:

- ``cd /usr/local/src``
- ``svn co http://svn.clozure.com/publicsvn/openmcl/release/1.11/linuxx86/ccl``
- ``cp /usr/local/src/ccl/scripts/ccl64 /usr/local/bin/ccl``


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



Installing pgloader on Ubuntu 11.04
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Ubuntu 11.04 stopped being supported in October 2012. Even if a pgloader build was possible to find for Ubuntu 11.04, it was likely to be very out of date, which would be a concern for porting correctness and being able to follow the online docs. So the preferred option was to build pgloader from source, using their `instructions <https://github.com/dimitri/pgloader/blob/master/INSTALL.md>`__ for doing so.

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


pgloader
........
This requires Common Lisp (such as CCL) and ``freetds-dev``.

``git clone`` from the `pgloader repository <https://github.com/dimitri/pgloader>`__.

``cd`` into the cloned directory and then type ``make CL=ccl DYNSIZE=256``.

- One possible error when missing ``freetds-dev`` is: ``error opening shared object "libsybdb.so"`` (`Source <https://github.com/dimitri/pgloader/issues/131>`__)

- One possible error when the CCL installation is not correct is: ``[package buildapp]...........  > Error: Error #<SILENT-EXIT-ERROR #x302000F5869D>  > While executing: (:INTERNAL MAIN), in process listener(1).`` (`Related link <https://github.com/dimitri/pgloader/issues/392>`__)

- If errors occur, remember to ``make clean`` before trying another ``make``, just in case.

When ``make`` finishes successfully, the ``pgloader`` executable should be in ``<pgloader directory>/build/bin``.



Installing pgloader on Ubuntu 14.04
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
pgloader `released version 3.3.1 <https://github.com/dimitri/pgloader/releases>`__ on 2016.08.28 with a new "bundle distribution". Unfortunately, this only works on SBCL.


CCL way
.......
Basically the same as the Ubuntu 11.04 method, but at this time of writing Ubuntu 14.04 is still supported, so getting the packages is a lot less tedious.

Get freetds-dev and its dependencies: ``sudo apt-get install freetds-dev``

Get pgloader: ``wget https://github.com/dimitri/pgloader/archive/v3.3.1.tar.gz`` then ``tar xzvf v3.3.1.tar.gz``.

cd in: ``cd pgloader-3.3.1``. Then run ``make CL=ccl DYNSIZE=256``.

When ``make`` finishes successfully, the ``pgloader`` executable should be in ``<pgloader directory>/build/bin``.


SBCL way
........
Install SBCL.

Do ``wget https://github.com/dimitri/pgloader/releases/download/v3.3.1/pgloader-bundle-3.3.1.tgz`` to get this distribution. Then ``tar xzvf pgloader-bundle-3.3.1.tgz``.

Then as the README says, run ``make``. This'll take a while. Once it completes, run ``LANG=en_US.UTF-8 make test`` to run the test suite.



(Old) pgloader from binary on Windows
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
This was initially used to test if pgloader seemed viable given our database structure.

Get an early 2015 pgloader binary `here <https://github.com/dimitri/pgloader/issues/159>`__, linked in the 4th comment. You'll also need sqlite3.dll from `here <https://www.sqlite.org/download.html>`__, plus libssl32.dll and libeay32.dll from `here <http://gnuwin32.sourceforge.net/packages/openssl.htm>`__; put those 3 .dll files in the same directory as the pgloader binary.

In the pgloader command run from command line, replace ``pgloader`` with whatever the pgloader executable name is.



Port the database using pgloader
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Ensure that the beta RDS instance's security group allows port 5432 (PostgreSQL) requests from the alpha server's IP.

Create a load command file, say ``coralnet.load``, with the following contents:

::
    
  load database
   from mysql://<usernamehere>:<passwordhere>@127.0.0.1/coralnet
   into postgresql://<usernamehere>:<passwordhere>@<RDS-instance-public-address-goes-here>:5432/coralnet
    
   WITH quote identifiers, include drop
    
   SET maintenance_work_mem to '64MB', work_mem to '4MB'
    
   CAST type date to date using zero-dates-to-null
    
   EXCLUDING TABLE NAMES MATCHING ~/celery/;

- For the MySQL location, ``localhost`` worked for our Ubuntu 11.04 system, and ``127.0.0.1`` worked for our Ubuntu 14.04 system. (`Related issue <https://github.com/dimitri/pgloader/issues/214>`__)
   
- Substitute the database users' usernames and passwords for ``<usernamehere>`` and ``<passwordhere>``. If you've been following the instructions here so far, the PostgreSQL username should be ``django``. Don't use the root/master user, because we need ``django`` to be the owner of the tables; this prevents permission errors later on when Django works with the database.

- Fill in ``<RDS-instance-public-address-goes-here>`` with the Public DNS of the RDS instance.

- After the hostname is the database name; change that if it's something other than ``coralnet``.

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

For us, this process takes about 45 minutes. At the end it'll display a table of results. Confirm that there are no errors.

Two possible warnings that should be acceptable are:

- ``Postgres warning: table "..." does not exist, skipping``. See `this link <http://pgloader.io/howto/sqlite.html>`__: "the WARNING messages we see here are expected as the PostgreSQL database is empty when running the command, and pgloader is using the SQL commands DROP TABLE IF EXISTS when the given command uses the include drop option."

- ``identifier "idx_20322_guardian_groupobjectpermission_object_pk_122874e9_uniq" will be truncated to "idx_20322_guardian_groupobjectpermission_object_pk_122874e9_uni"``. To our knowledge at least, there's nothing that would break if an index were renamed.

At this point, it's a good idea to make a snapshot of the RDS instance, in case we make a mistake on the Django migration steps. You can create a snapshot from Amazon's RDS Dashboard.


Hanging issue
.............
In some cases, pgloader will seem to get stuck at a certain part of the porting process and hang forever. One way to confirm that it's getting stuck is to check the RDS dashboard's activity graph for the beta RDS instance. If no Write IOPs have happened for a while, it's probably stuck.

If it gets stuck:

- Kill the pgloader process.

- Check your tables' row counts in the alpha and beta servers. See where they don't match, and use that to figure out how far the process got before getting stuck.

  - There is probably a fancy command to output row counts for all tables at once, but if you're not in a hurry then you can do one table at a time: ``select count(*) from <table name>;`` works in both MySQL and PostgreSQL.

- Modify ``coralnet.load`` to port smaller parts of the database at a time to prevent hanging (see `this issue <https://github.com/dimitri/pgloader/issues/337>`__). For example, you could run pgloader five times, each time with different table-name clauses:

::

  EXCLUDING TABLE NAMES MATCHING ~/celery/, ~/annotations_annotation/, ~/images_/, ~/reversion_version/, ~/sentry/;

::

  INCLUDING ONLY TABLE NAMES MATCHING ~/annotations_annotation/;

::

  INCLUDING ONLY TABLE NAMES MATCHING ~/images_/;

::

  INCLUDING ONLY TABLE NAMES MATCHING ~/reversion_version/;

::

  INCLUDING ONLY TABLE NAMES MATCHING ~/sentry/;

In 2016.11, going from Ubuntu 14.04 alpha to a production-configured beta RDS instance, these commands took 1m09s, 4m55s, 3m48s, 29m33s, and 1m25s respectively.


.. _beta_migration_django_migrations:

Django migrations
-----------------
These are the migrations that the alpha production DB must run to get completely up to date with the latest Django and repo code.

The migration numbers are in Django's new migration framework unless specifically denoted as South migrations.

SSH into the beta server, activate the environment, and run these in order (correct as of 2016.11):

- contenttypes: fake 0001, run 0002
- auth: fake 0001, run 0002-0007
- admin: fake 0001, run 0002
- sessions: fake 0001
- guardian: fake 0001
- easy_thumbnails: fake 0001, run 0002 (OR run South's 0016, then fake new 0001-0002) (**this was wrong; see details below**)
- reversion: run South's 0006-0008, then fake new 0001, then run new 0002 (see details below)
- Our apps:

  - accounts: fake 0001-0002
  - images: fake 0001
  - annotations: fake 0001-0003
  - bug_reporting: fake 0001
  - Run the rest in any order

Example commands: ``python manage.py migrate contenttypes 0001 --fake``, ``python manage.py migrate contenttypes 0002``, ``python manage.py migrate auth 0001 --fake``, ``python manage.py migrate auth 0007``, etc.

You'll get message(s) like ``The following content types are stale and need to be deleted``. Just to be safe, do all these deletions at the very end, when all migrations have been completed. Then go ahead and answer yes to the "Are you sure?" prompt(s).

- In our case, we have 1 stale contenttype in auth, 4 in annotations, and 7 in images.

- See more info about stale content types at `this link <http://stackoverflow.com/questions/16705249/stale-content-types-while-syncdb-in-django>`__. Note that we don't define any foreign keys to ``ContentType``.

Notable time-consuming migrations as of 2016.11:

- reversion (South) 0006: 3 minutes
- images 0004-0015: 55 minutes combined

After running these migrations, make another snapshot of the RDS instance.


contenttypes
~~~~~~~~~~~~
The reason these migrations should be run first is that, if you don't run the ``contenttypes`` migrations early enough, you may get ``RuntimeError: Error creating new content types. Please make sure contenttypes is migrated before trying to migrate apps individually.`` `Link 1 <http://stackoverflow.com/questions/29917442/error-creating-new-content-types-please-make-sure-contenttypes-is-migrated-befo>`__, `Link 2 <https://code.djangoproject.com/ticket/25100>`__

In fact, you may get that message after faking ``contenttypes`` 0001. This doesn't seem to have any consequence though; just proceed to real-migrate 0002 and you shouldn't see the message again.


reversion
~~~~~~~~~
``reversion`` is tricky. Before our beta upgrading process, we had reversion 1.5.1, and that had South migrations numbered up to 0005. But just before reversion switched to the new migrations, they had made South migrations up to 0008. Then they merged the South migrations 0001-0008 into a new 0001 to make things cleaner.

To apply the ``reversion`` migrations:

- pip-install ``Django==1.6``, ``django-reversion==1.8.4``, and ``South``.
- Add ``'south'`` to your ``INSTALLED_APPS`` setting.
- Comment out all other apps in ``INSTALLED_APPS`` except for Django core apps, south, and reversion. This is probably the simplest way to avoid South errors about other apps having `ghost migrations <http://stackoverflow.com/questions/8875459/what-is-a-django-south-ghostmigrations-exception-and-how-do-you-debug-it>`__. Also comment out ``errorlogs`` since the app setup is post-Django-1.6.
- Change the ``DATABASES`` setting's engine to ``'postgresql_psycopg2'`` to make Django 1.6 happy. (This is the same engine, just under a different name.)
- Comment out the celery line in ``config/__init__.py`` to make Django 1.6 happy (``django.setup()`` didn't exist yet).
- Use ``manage.py migrate --list`` to confirm that ``reversion`` has run migrations 0001 to 0005.
- Use ``manage.py migrate reversion`` to run migrations 0006 to 0008.
- Revert all the code changes. ``git checkout config/settings/base.py``, etc.
- pip-install the latest ``Django`` and ``django-reversion`` again, and uninstall ``South``.
- Now you can see with ``manage.py showmigrations`` that the ``reversion`` migration numbers have changed. Fake-run 0001, then run 0002.


easy_thumbnails
~~~~~~~~~~~~~~~
Shortly after beta release, we found out that our ``easy_thumbnails_source`` and ``easy_thumbnails_thumbnail`` tables were not having their ``unique_together`` constraints applied when saving thumbnails. This caused the error ``MultipleObjectsReturned at /image/<id>/annotation/tool/ get() returned more than one Source -- it returned 2!``

It seems we were mistaken in assuming the alpha database state was at South migration 0015. In reality, it seems alpha was at South migration 0013:

- From South migration 0001 to 0012, at least one of the tables ``Storage`` and ``StorageNew`` existed in easy_thumbnails.
- Starting from South migration 0013, neither of ``Storage`` or ``StorageNew`` exist in the migration state.
- Neither of ``easy_thumbnails_storage`` or ``easy_thumbnails_storagenew`` exist in the alpha database, indicating that it was at least at 0013.
- South migrations 0014 and 0015 create the ``unique_together`` indexes which are missing from our tables.

The reason we need this "which migrations have been run?" deduction is that the alpha database does not have any records of which easy_thumbnails South migrations were run in the past. One version of easy_thumbnails we used in the past caused problems with its South migrations directory location, so that may be part of the reason for the missing records.

In conclusion, the correct procedure was: **fake South's 0001-0013, then run South's 0014-0015, then fake new 0001, then run new 0002**.

After beta release, though, we didn't really have the luxury of re-running these migrations from scratch. Here's how we patched the situation:

- Find the duplicate easy_thumbnails objects with the following code:

  ::

    from easy_thumbnails.models import Source, Thumbnail
    sources = Source.objects.all().order_by('pk')
    source_name_set = set()
    dupe_sources = []
    for obj in sources:
        if obj.name in source_name_set:
            print("Source {pk} *** {name}".format(pk=obj.pk, name=obj.name))
            dupe_sources.append(obj)
        else:
            source_name_set.add(obj.name)
    thumbnails = Thumbnail.objects.all().order_by('pk')
    thumbnail_name_set = set()
    dupe_thumbnails = []
    for obj in thumbnails:
        if obj.name in thumbnail_name_set:
            print("Thumbnail {pk} *** {name}".format(pk=obj.pk, name=obj.name))
            dupe_thumbnails.append(obj)
        else:
            thumbnail_name_set.add(obj.name)

- There were 14 duplicate Sources and hundreds of duplicate Thumbnails. There's no reason why we should lose the original images by deleting easy_thumbnails' objects, but to satisfy our paranoia, we went into S3 and manually backed up the original files of the 14 duplicate Sources (found by filename-searching each of the printed Source names in the S3 console) before deleting the Sources.

- Delete the duplicate objects:

  ::

    for t in dupe_thumbnails:
        t.delete()
    for s in dupe_sources:
        s.delete()

- Use ``manage.py sqlmigrate easy_thumbnails 0001_initial`` to see the database-level SQL commands required to create the ``unique_together`` constraints. (This management command just prints the SQL that the migration is equivalent to.)

- Open pgAdmin, connect to our database, and run those SQL commands - took about 15 seconds total:

  ::

    ALTER TABLE "easy_thumbnails_source" ADD CONSTRAINT "easy_thumbnails_source_storage_hash_481ce32d_uniq" UNIQUE ("storage_hash", "name");
    ALTER TABLE "easy_thumbnails_thumbnail" ADD CONSTRAINT "easy_thumbnails_thumbnail_storage_hash_fb375270_uniq" UNIQUE ("storage_hash", "name", "source_id");
    COMMIT;

- In pgAdmin, check the SQL tab for the easy_thumbnails tables to ensure that the table definitions now have the unique constraints.

- Check for the original files' existence in S3 again.

One last note of interest: `A similar "Multiple objects returned" issue <https://github.com/SmileyChris/easy-thumbnails/issues/69>`__ was reported to easy_thumbnails back in 2011. The fix was to create South migration 0015, which was one of the migrations we had missed. The issue thread suggests that the issue tended to happen with cloud storage rather than local storage, which also applies to our beta migration.
