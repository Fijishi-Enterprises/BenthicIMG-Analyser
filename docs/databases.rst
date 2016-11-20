.. _databases:

Databases
=========

The exact setup procedure will differ depending on whether you want a database local to your machine, or a database on Amazon RDS.


Installing PostgreSQL server and client
---------------------------------------

- *Local database*

Download and install the PostgreSQL server/core, 9.6.x. 32 or 64 bit shouldn't matter.

- On Linux, the package will probably be ``postgresql-<version number>``.
- During the setup process, make sure you keep track of the root password.

Locate and open the client program that came with PostgreSQL. Windows has pgAdmin, while Linux should have the command-line ``postgresql-client-<version number>`` or the GUI pgAdmin as options (may be distributed separately).

Using the client program, check that you can connect to the PostgreSQL server.


Installing PostgreSQL client only
---------------------------------

- *RDS database*

Download and install the PostgreSQL client only, corresponding to 9.6.x. 32 or 64 bit shouldn't matter. Windows has pgAdmin, while Linux should have the command-line ``postgresql-client-<version number>`` or the GUI pgAdmin as options (may be distributed separately).


Setting up an Amazon RDS instance (RDS route)
---------------------------------------------

- *RDS database*

Go to the Amazon EC2 console. Create a Security Group which allows inbound connections on port 5432 (the standard PostgreSQL port) from the machine with your PostgreSQL client (probably either your local machine or an EC2 instance).

- Use a site like `whatismyip.com <https://www.whatismyip.com/>`__ to find your local IP.

Go to the Amazon RDS console. Create a PostgreSQL instance.

- Select No to the "Production?" question. The Yes settings are generally out of our budget.
- Select PostgreSQL version 9.6.x.
- Select db.t2.medium for production, db.t2.micro for staging.

  - Again, strict budgeting here. t2.medium might still be a bit expensive for us.

- Specify at least 30 GB of Allocated Storage (this is just based on our database size, about 15 GB at the end of alpha). If you answered Yes to "Production?" then the minimum might be greater than 30 GB.
- Select Yes on the Publicly Accessible option.

  - (TODO: Can this be No for production after initial DB configuration? Is SQS able to access the database with No? Is there any reason we'd need to inspect the data in pgAdmin as opposed to manage.py dbshell?)

- Assign the Security Group mentioned above.
- You can specify the Database Name for the primary database which Django will connect to (e.g. ``coralnet``). You can also create the database manually later.
- Database Port should be the default, 5432.
- (TODO: Should we Enable Encryption for production (`Link <http://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/Overview.Encryption.html>`__)?

Once the RDS instance is created, open your PostgreSQL client (e.g. pgAdmin) and try logging in as the master user you created.


Set up a user and database
--------------------------

- *Local database*
- *RDS database*

Connect to the PostgreSQL server as the ``postgres`` or ``master`` user.

Create another user for the Django application to connect as. We'll say the user's called ``django``. Ensure ``django`` has permission to create databases (this is for running unit tests).

- In pgAdmin 4: Right-click Login/Group Roles, Create -> Login/Group Role..., Name = ``django``. Go to Definition tab and add password. Go to Privileges tab, Yes on "Can login?", Yes on "Create databases?". Save.

Create a database; we'll say it's called ``coralnet``. Owner = ``django``, Encoding = UTF8 (`Django says so <https://docs.djangoproject.com/en/dev/ref/databases/#optimizing-postgresql-s-configuration>`__). Defaults for other options should be fine.

- If you already created the database you want as part of the RDS instance setup, just ensure the settings are correct.

Make sure that ``django`` has USAGE and CREATE privileges in the ``coralnet`` database's ``public`` schema. In particular, this might not be done by default in RDS.

- In pgAdmin 4: Expand the ``coralnet`` database, expand ``Schemas``, right click the ``public`` schema, Properties..., Security tab. Ensure there's a row with Grantee ``django`` and Privileges ``UC``.

Optimization recommended by Django: set some default parameters for database connections. `See the docs page <https://docs.djangoproject.com/en/dev/ref/databases/#optimizing-postgresql-s-configuration>`__. Can either set these for the ``django`` user with ``ALTER_ROLE``, or for all database users in ``postgresql.conf``.

- ``ALTER_ROLE`` method in pgAdmin 4: Right click the ``django`` Login Role, Properties..., Parameters tab. Use the + button to add an entry. Database = ``coralnet``, Name and Value = whatever is specified in that Django docs link.

Two more notes:

- When you create the ``coralnet`` database, it'll have ``public`` privileges by default. This means that every user created in that PostgreSQL installation has certain privileges by default, such as connecting to that database. `Related SO thread <http://stackoverflow.com/questions/6884020/why-new-user-in-postgresql-can-connect-to-all-databases>`__. This shouldn't be an issue as long as we don't have any PostgreSQL users with insecure passwords.

- A Django 1.7 release note says: "When running tests on PostgreSQL, the USER will need read access to the built-in postgres database." This doesn't seem to be a problem by default, probably due to the default ``public`` privileges described above.


.. _database_porting:

Porting data into the database
------------------------------

- *Staging server*
- *Alpha to beta server migration*

If syncing data from the production to the staging database:

- Edit the RDS Security Group to also allow inbound port-5432 connections from an EC2 instance's security group. (In the Source column, type ``sg`` and these security group choices should appear.)

- Install ``postgresql-client-common`` and ``postgresql-client-<version>`` on the EC2 instance.

- Create a ``~/.pgpass`` file so that the following commands don't require password typing. In particular, the dump and restore command would be otherwise impossible to run because it would ask for two passwords at once. (`Link 1 <http://dba.stackexchange.com/questions/14740/>`__, `Link 2 <https://www.postgresql.org/docs/current/static/libpq-pgpass.html>`__)

  - Open ``~/.pgpass`` with a text editor. Add two lines of the format ``hostname:port:database:username:password``. One line should correspond to production, one line should correspond to staging. The staging line, however, should have ``*`` for the database. (This covers the drop and create commands; perhaps these commands aren't seen as "belonging" to a particular database.)

  - ``chmod 0600 ~/.pgpass``. As PostgreSQL's docs say, "If the permissions are less strict than this, the file will be ignored."

- Drop the staging database.

  - ``dropdb -h <staging instance hostname> -U <staging instance user> <staging DB name>``

- Recreate the staging database.

  - ``createdb -h <staging instance hostname> -U <staging instance user> --owner=<staging instance user> --encoding=UTF8 <staging DB name>``

- Use dump on the production database and restore on the staging database. Note that no intermediate file is needed between dump and restore. (`Link <http://stackoverflow.com/a/1238305/>`__)

  - ``pg_dump -C -h <production instance hostname> -U <production instance user> --no-owner -t 'public.*' <production DB name> | psql -h <staging instance hostname> -U <staging instance user> <staging DB name>``

  - The command takes about 40 minutes to complete as of 2016.11. You'll probably see it taking a while at the lines ``ALTER TABLE`` and ``CREATE INDEX``.

  - ``-t`` means all tables matching this. ``-t 'public.*'`` says to get all tables in the public schema. Not specifying this gets some crazy permission denied / invalid command stuff that never ends.

    - "When using wildcards, be careful to quote the pattern if needed to prevent the shell from expanding the wildcards". (`Link <https://www.postgresql.org/docs/9.5/static/app-pgdump.html>`__)

  - ``-C`` adds CREATE statements (e.g. CREATE table, presumably). Doesn't seem to create the database though, so we still need the ``createdb`` step.

  - ``--no-owner`` ensures that the dump doesn't create tables with the previous owner intact. It's needed in our case because the source DB and destination DB have different owners.

If doing the beta migration process:

- Edit the RDS Security Group to also allow inbound port-5432 connections from the IP of the machine running pgloader.
- :ref:`Migrate the data from alpha to beta <beta_migration_database>`.


Upgrading PostgreSQL version
----------------------------

If using RDS, minor version upgrades (e.g. 9.6.0 to 9.6.1) should be done automatically if you specified this behavior in the instance creation options.

Otherwise: (TODO)

(TODO: See if upgrading a non-minor version also means ``psycopg2`` should be re-installed with a corresponding upgraded version of ``libpg-dev``.)