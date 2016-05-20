2016 database migration
=======================


Notes about pgloader
--------------------
`pgloader <http://pgloader.io/index.html>`__ seems to be one of the best tools out there for porting a MySQL database to PostgreSQL. It takes a live database or CSV file as input, and outputs to a live PostgreSQL database. If we have live databases on both sides, then we don't even need to have a separate database dumping step, which should reduce the possible points of failure / data corruption.

At first the plan was to install pgloader on an AWS instance and connect to the UCSD CSE machine's MySQL database through the network. However, all attempts to the UCSD CSE machine's MySQL failed, even after disabling the ufw (firewall) configuration. Perhaps the UCSD CSE machine's router had a firewall which we didn't have control over. We briefly considered contacting CSE Help about it, but then decided not to give them another reminder about our very outdated server machine.

We ended up installing pgloader on the UCSD CSE machine, so that the MySQL connection would be local, and the PostgreSQL connection would be to the AWS instance (which has no firewall problems). We initially ruled out this idea because the UCSD CSE machine's Ubuntu is 11.04, a version that's no longer supported. However, it turned out to be possible.


Install pgloader on the UCSD CSE machine 
----------------------------------------
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




Port the database using pgloader
--------------------------------
Create a load file, say ``coralnet.load``, with the following contents:

::
    
  load database
   from mysql://<usernamehere>:<passwordhere>@localhost/coralnet
   into postgresql://<usernamehere>:<passwordhere>@<RDS-instance-public-address-goes-here>:5432/coralnet
    
   WITH quote identifiers, include drop, create no indexes
    
   SET maintenance_work_mem to '256MB', work_mem to '32MB'
    
   CAST type date to date using zero-dates-to-null
    
   EXCLUDING TABLE NAMES MATCHING ~/celery/;
   
Substitute the database users' usernames and passwords for ``<usernamehere>`` and ``<passwordhere>``. Also fill in ``<RDS-instance-public-address-goes-here>``. After the hostname is the database name; change that if it's something other than ``coralnet``.

Explanations:
   
- ``quote identifiers`` is needed so that upper/lower case of identifiers are maintained. This is important for some of our column names like ``annotatedByHuman``.
   
- ``include drop`` makes pgloader automatically drop the table named X in the target PostgreSQL database if the operation includes porting over table X. This allows us to conveniently retry the porting operation from scratch if something fails the first time.

  - Note that this drop will cascade to all objects referencing the target tables, possibly including tables that are not being ported over. However, if we're porting over the whole database at once, then it's not a problem.
   
- ``create no indexes`` tells pgloader to not create indexes as it ports the data over. This is just to speed up the porting process.
   
- ``SET maintenance_work_mem to '256MB', work_mem to '32MB'`` sets PostgreSQL parameters (these aren't pgloader parameters) on the amount of memory to use during certain operations. See the PostgreSQL docs for `work_mem <http://www.postgresql.org/docs/current/static/runtime-config-resource.html#GUC-WORK-MEM>`__ and `maintenance_work_mem <http://www.postgresql.org/docs/current/static/runtime-config-resource.html#GUC-MAINTENANCE-WORK-MEM>`__. Check the RDS instance's memory capacity to get an idea of what values to use.
   
- ``CAST type date to date using zero-dates-to-null`` is a casting rule which says to cast MySQL ``date`` types to PostgreSQL ``date`` types, using pgloader's transformation function which converts any ``0000-00-00`` dates to ``NULL``.

  - pgloader uses this transformation function by default only if the MySQL column's default value is ``0000-00-00``. Our ``images_metadata`` table's ``photo_date`` column doesn't have a default value because it accepts NULL values. However, we do have a few ``photo_date`` values which are ``0000-00-00``, perhaps because the column used to be non-NULL. Therefore, we DO have zero dates to convert, yet our column doesn't match pgloader's default rules for converting zero dates, so we define our own rule.
  
  - Defaulting to ``0000-00-00`` is standard MySQL behavior: `Link <http://dev.mysql.com/doc/refman/5.5/en/datetime.html>`__, `Another link (possibly on old MySQL versions) <http://sql-info.de/mysql/gotchas.html#1_14>`__
   
- ``EXCLUDING TABLE NAMES MATCHING ~/celery/`` excludes tables whose names match the regular expression ``celery``. This should exclude all the ``celery_<name>`` and ``djcelery_<name>`` tables; we don't need these tables any longer, and at least one of them is quite large.

- The newlines and amount of whitespace shouldn't matter. There must be a semicolon after the last command.

- See the `pgloader docs <http://pgloader.io/howto/pgloader.1.html>`__ for more details.

Run pgloader: ``<pgloader directory>/build/bin/pgloader coralnet.load``

For us, this process might take about 1 hour. Confirm that there are no errors.

At this point, it's a good idea to make a snapshot of the RDS instance, in case we make a mistake on the Django migration steps. You can create a snapshot from Amazon's RDS Dashboard.




Django migrations
-----------------
TODO
