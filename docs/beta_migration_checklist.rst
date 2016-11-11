Beta migration checklist
========================

Phase 1

- Rename the existing EC2 server instance to staging. Ensure the Django setup uses staging settings, not production settings.
- `Create and set up an EC2 instance <server_instances>`__ for the beta production server. Make it a t2.large.
- RDS

  - `Create a new RDS instance and database <databases>`__. Ensure the RDS instance has backups, termination protection, and other production-appropriate settings. Make it 30 GB (it can be expanded later).

    - The idea is to put production-relevant settings (which may come with extra costs) on the production instance, and more basic settings on the staging instance. Not using production settings for both databases should, in theory, save money.

  - `Migrate the alpha server database to the new RDS instance's database <beta_migration_database>`__.
  - The old RDS instance currently has two databases which are largely copies of each other. Delete one of these databases, and keep the other database for staging. Rename the instances and databases appropriately.
  - Check the staging RDS instance's settings; if there's any safety features that can be turned off or toned down to cut costs, then do so.

- S3

  - We currently have two S3 buckets which are copies of the alpha-server media files from around 2016.07. Pick one to be the beta production server's bucket, and name it production. Name the other bucket staging.
  - `Sync files from the beta staging S3 bucket to the new S3 bucket <sync_between_s3_buckets>`__.
  - `Sync files from the alpha server filesystem to the new S3 bucket <sync_filesystem_to_s3>`__. This sync will be much slower per-file, but it should just be a partial sync.
  - Run a script to check that our new database doesn't reference any image files that don't exist in our new S3 bucket.

- `Set up Git on the EC2 instance <git>`__.
- `Set up Python and Django on the EC2 instance <python_and_django>`__, with staging settings.
- `Run Django migrations <beta_migration_django_migrations>`__.
- `Set up a gunicorn + nginx web server on the EC2 instance <web_server>`__.
- `Set up the vision backend <backend>`__.
- Run unit tests. Look at the running website to see that all types of database data seem intact.
- `Add convenience scripts <scripts>`__ somewhere on the EC2 instance, with simple names such as ``setup_env.sh``, ``server_start.sh``, and ``server_stop.sh``.

Phase 2

- Contact the UCSD hostmaster. Get things ready to switch coralnet.ucsd.edu to the AWS beta server.
- Once the hostmaster related timeframe is under control, email users about the alpha site closing date/time.
- Switch the beta server from staging to "pre-production" settings so that email isn't faked anymore. The only difference from production now should be ``ALLOWED_HOSTS``.
- `Generate a TLS certificate <tls>`__ for the current amazonaws URL. This is for testing TLS during this phase.
- Implement HTTPS/SSL/TLS on the beta server using that certificate.
- `Add a Postfix email server <postfix>`__ (also secured with TLS) to the beta server. Test (being careful to not email any non-admins).
- Review Django's security docs.
- Look for minor bugs to fix.

Phase 3

- Wait until the alpha site closing date/time.
- Take the alpha server down. (TODO: Details)
- `Migrate the alpha server database to the new RDS instance <beta_migration_database>`__.
- `Sync files from the alpha server filesystem to the new S3 bucket <sync_filesystem_to_s3>`__. This sync should just involve the new files since Phase 1.
- Ensure all ``secrets.json`` details on the beta server are correct.
- Switch coralnet.ucsd.edu to the beta server.
- Switch the beta server from pre-production to production settings. ``ALLOWED_HOSTS`` should only have coralnet.ucsd.edu now.
- Generate a TLS certificate for the coralnet.ucsd.edu domain.
  - Generating a new certificate seems safer than transferring the old certificate over the network from the alpha server.
- Ensure the AWS security group for the beta server allows port 80 (HTTP) and 443 (HTTPS) access from any IP, not just developers' IPs.
- Let users know that the site is back up, and point them to the "What's new in beta" guide.