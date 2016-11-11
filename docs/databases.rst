.. _databases:

Databases
=========

The exact setup procedure will differ depending on whether you want a database local to your machine, or a database on Amazon RDS.


Installing PostgreSQL server and client
---------------------------------------

- *Local database*

Download and install the PostgreSQL server/core, 9.5.1. (TODO: Look into 9.6.x.) 32 or 64 bit shouldn't matter.

- On Linux, the package will probably be ``postgresql-<version number>``.
- During the setup process, make sure you keep track of the root password.

Locate and open the client program that came with PostgreSQL. Windows has pgAdmin, while Linux should have the command-line ``postgresql-client-<version number>`` or the GUI pgAdmin as options (may be distributed separately).

Using the client program, check that you can connect to the PostgreSQL server.


Installing PostgreSQL client only
---------------------------------

- *RDS database*

Download and install the PostgreSQL client only, 9.5.1. (TODO: Look into 9.6.x.) 32 or 64 bit shouldn't matter. Windows has pgAdmin, while Linux should have the command-line ``postgresql-client-<version number>`` or the GUI pgAdmin as options (may be distributed separately).


Setting up an Amazon RDS instance (RDS route)
---------------------------------------------

- *RDS database*

Go to the Amazon EC2 dashboard. Create a Security Group which allows inbound connections on port 5432 (the standard PostgreSQL port) from the machine with your PostgreSQL client (probably either your local machine or an EC2 instance).

- Use a site like `whatismyip.com <https://www.whatismyip.com/>`__ to find your local IP.

Go to the Amazon RDS dashboard. Create a PostgreSQL 9.5.x RDS instance. (TODO: Look into 9.6.x)

- Assign the Security Group that you just created.
- Select Yes on the Publicly Accessible option.
- Make sure the Database Port is the default, 5432.

Once the RDS instance is created, open your PostgreSQL client (e.g. pgAdmin) and try logging in as the master user you created.


Set up a user and database
--------------------------

- *Local database*
- *RDS database*

Connect to the PostgreSQL server as the ``postgres`` or ``master`` user.

Create a user for the Django application to connect as. We'll say the user's called ``django``.

- In pgAdmin: Right-click Login Roles, New Login Role..., Role name = ``django``, go to Definition tab and add password.

Create a database; we'll say it's called ``coralnet``. Owner = ``django``, Encoding = UTF8 (`Django says so <https://docs.djangoproject.com/en/dev/ref/databases/#optimizing-postgresql-s-configuration>`__). Defaults for other options should be fine.

- If you already created the database you want as part of the RDS instance setup, skip this step.

Make sure that ``django`` has USAGE and CREATE privileges in the ``coralnet`` database's ``public`` schema. In particular, this might not be done by default in RDS.

- In pgAdmin: Expand the ``coralnet`` database, expand ``Schemas``, right click the ``public`` schema, Properties..., Privileges tab.

Make sure ``django`` has permission to create databases. This is for running unit tests.

- In pgAdmin: Right click ``django`` login role, Properties..., Role privileges tab, check "Can create databases".

Optimization recommended by Django: set some default parameters for database connections. `See the docs page <https://docs.djangoproject.com/en/dev/ref/databases/#optimizing-postgresql-s-configuration>`__. Can either set these for the ``django`` user with ``ALTER_ROLE``, or for all database users in ``postgresql.conf``.

- ``ALTER_ROLE`` method in pgAdmin: Right click the ``django`` Login Role, Properties, Variables tab. Database = ``coralnet``, Variable Name and Variable Value = whatever is specified in that Django docs link. Click Add/Change to add each of the 3 variables. Click OK.

Two more notes:

- When you create the ``coralnet`` database, it'll have ``public`` privileges by default. This means that every user created in that PostgreSQL installation has certain privileges by default, such as connecting to that database. `Related SO thread <http://stackoverflow.com/questions/6884020/why-new-user-in-postgresql-can-connect-to-all-databases>`__. This shouldn't be an issue as long as we don't have any PostgreSQL users with insecure passwords.

- A Django 1.7 release note says: "When running tests on PostgreSQL, the USER will need read access to the built-in postgres database." This doesn't seem to be a problem by default, probably due to the default ``public`` privileges described above.


.. _database_porting:

Porting data into the database
------------------------------

- *Staging server*
- *Alpha to beta server migration*

If syncing data from the production to the staging database:

- TODO: Probably something involving ``pg_dump``

If doing the beta migration process:

- Edit the Security Group to also allow inbound port-5432 connections from the IP of the machine running pgloader.
- Follow the instructions at this section: :ref:`beta-migration-pgloader`


Upgrading PostgreSQL version
----------------------------

TODO