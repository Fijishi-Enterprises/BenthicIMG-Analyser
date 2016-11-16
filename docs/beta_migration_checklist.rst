Beta migration checklist
========================

Phase 1

- RDS part 1

  - :ref:`Create a new RDS instance and database <databases>`, separate from the staging database's instance.

    - The idea is to put production-relevant settings (which may come with extra costs) on the production instance, and more basic settings on the staging instance. Not using production settings for both databases should, in theory, save money.

  - :ref:`Migrate the alpha server database to the new RDS instance's database <beta_migration_database>`.

- S3

  - We currently have two S3 buckets (``coralnet-serve-1`` and ``coralnet-website-serve-staging``) which are copies of the alpha-server media files from around 2016.07. We now want two buckets called ``coralnet-production`` and ``coralnet-staging``. There is no way to rename a bucket, so this requires several steps.
  - :ref:`Create a bucket <s3_bucket_setup>` called ``coralnet-production``.
  - :ref:`Create a bucket <s3_bucket_setup>` called ``coralnet-staging``.
  - :ref:`Sync files <sync_between_s3_buckets>` from one of the old buckets to ``coralnet-production``. (Seems to take 7-8 hours)
  - :ref:`Sync files from the alpha server filesystem <sync_filesystem_to_s3>` to ``coralnet-production``. Account for mappings between old/new directory names. This sync will be much slower per-file, but it should just be a partial sync, getting just the past 4 months' updates.
  - Run a script to check that ``coralnet-production`` doesn't reference any image files that don't exist in our new S3 bucket. (This should be the case since we synced DB before S3.)
  - :ref:`Sync files <sync_between_s3_buckets>` from ``coralnet-production`` to ``coralnet-staging``.
  - Delete the two old buckets when we're sure we don't need them anymore.

- EC2 part 1

  - Rename the existing EC2 server instance to staging. Ensure the Django setup uses staging settings, not production settings.
  - :ref:`Create and set up an EC2 instance <server_instances>` for the beta production server. Make it a t2.large. We'll use the default storage choice (8 GiB EBS volume, general purpose SSD) since we don't know if we need anything better yet.
  - :ref:`Set up Git on the EC2 instance <git>`.
  - :ref:`Set up Python and Django on the EC2 instance <python_and_django>`, with staging settings.

- RDS part 2

  - :ref:`Run Django migrations <beta_migration_django_migrations>` on the new production database to get it up to date with the current code.
  - The old RDS instance currently has two databases which are largely copies of each other. Delete one of these databases, and keep the other database for staging. Rename the instances and databases appropriately.
  - :ref:`Port the production database's data to the staging database <database_porting>`, since staging hasn't been synced since 2016.05.
  - Check the staging RDS instance's settings; if there's any safety features that can be turned off or toned down to cut costs, then do so.

- EC2 part 2

  - :ref:`Set up a gunicorn + nginx web server on the EC2 instance <web_server>`.
  - :ref:`Set up the vision backend <backend>`.
  - Run unit tests. Look at the running website to see that all types of database data seem intact.
  - :ref:`Add convenience scripts <scripts>` somewhere on the EC2 instance, with simple names such as ``setup_env.sh``, ``server_start.sh``, and ``server_stop.sh``.
  - Add convenience symlinks: ``/cnhome`` -> ``/srv/www/coralnet``, and ``/scripts`` -> ``/srv/www/scripts``.

Phase 2

- Contact the UCSD hostmaster. Get things ready to switch coralnet.ucsd.edu to the AWS beta server.
- Once the hostmaster related timeframe is under control, email users about the alpha site closing date/time.
- Switch the beta server from staging to "pre-production" settings so that email isn't faked anymore. The only possible difference from production now should be ``ALLOWED_HOSTS``.
- :ref:`Generate a TLS certificate <tls>` for the current amazonaws URL. This is for testing TLS during this phase.
- Implement HTTPS/SSL/TLS on the beta server using that certificate.

  - With the site now in HTTPS, see if the S3 bucket policy's Referer line needs to be updated.

- :ref:`Add a Postfix email server <postfix>` (also secured with TLS) to the beta server. Test (being careful to not email any non-admins).
- Review Django's security docs.
- Look for minor bugs to fix.

Phase 3

- Wait until the alpha site closing date/time.
- Take the alpha server down. (TODO: Details)
- :ref:`Migrate the alpha server database to the new RDS instance <beta_migration_database>`. (20m work, 40m waiting)
- :ref:`Update the code on the beta server <update_server_code>`.
- Since the database was reset to alpha, :ref:`run all Django migrations <beta_migration_django_migrations>`. (20m work, 60m waiting)
- :ref:`Sync files from the alpha server filesystem to the production S3 bucket <sync_filesystem_to_s3>`. This sync should just involve the new files since Phase 1. (2-3h waiting)
- :ref:`Reset production S3 file permissions to private <s3_reset_file_permissions>`__.
- Ensure all ``secrets.json`` details on the beta server are correct.
- Switch coralnet.ucsd.edu to the beta server.
- Switch the beta server from pre-production to production settings (if this entails changing anything).
- Generate a TLS certificate for the coralnet.ucsd.edu domain.

  - Generating a new certificate seems safer than transferring the old certificate over the network from the alpha server.

- With the site now under a different domain, see if the S3 bucket policy's Referer line needs to be updated.
- Ensure the AWS security group for the beta server allows port 80 (HTTP) and 443 (HTTPS) access from any IP, not just developers' IPs.
- Let users know that the site is back up, and point them to the "What's new in beta" guide.