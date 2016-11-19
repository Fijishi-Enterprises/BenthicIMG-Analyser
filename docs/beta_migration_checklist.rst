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
    - ``python manage.py checkformissingimages``. Took only 2 minutes to run. 0 missing files identified out of 317363 Image objects checked.
  - :ref:`Sync files <sync_between_s3_buckets>` from ``coralnet-production`` to ``coralnet-staging``.
    - With ``coralnet-staging`` starting empty, this took roughly 5 hours.
  - Delete the two old buckets when we're sure we don't need them anymore.
    - If you attempt this from the S3 console, you'll get an error: ``There are more than 100000 objects (including versions) in <bucket name>.`` You need to use one of the methods `here <https://docs.aws.amazon.com/AmazonS3/latest/dev/delete-or-empty-bucket.html>`__ to delete the buckets. Since we didn't enable versioning on these old buckets, ``aws s3 rb s3://<bucket-name> --force`` should work. This takes about 35 minutes per bucket currently.

- EC2 part 1

  - On the EC2 console's instances view, rename the existing EC2 server instance to staging. Ensure the Django setup uses staging settings, not production settings.
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
  - :ref:`Add convenience scripts <scripts>` somewhere on the EC2 instance, with simple names such as ``env_setup.sh``, ``run_server.sh``, and ``stop_server.sh``.
  - Add convenience symlinks: ``/cnhome`` -> ``/srv/www/coralnet``, and ``/scripts`` -> ``/srv/www/scripts``.

Phase 2

- Set up the staging server as a proxy for the alpha server. That way, if the coralnet.ucsd.edu IP switch completes much sooner than expected, the domain should end up pointing to this staging server, which points to the alpha server, meaning nothing will appear different.

  - Give our production elastic IP to the staging server for now.
  - Write an ``nginx.conf`` for the staging server that looks something like this:

    ::

      server_tokens off;
      server {
          location / {
              proxy_pass http://<alpha server's bare IP>;
              proxy_read_timeout 604800s;
              client_max_body_size 100m;
          }
      }

  - Test the proxy setup by typing the staging server's IP in your browser's address bar. It should show the alpha server's site. Two points of interest:

    - Emails. The SSL certificate the alpha server uses only works for the host coralnet.ucsd.edu, not the staging server's IP. However, the alpha server's email system doesn't seem to care what the specified host on the web request was - whether it's the staging server's IP, the alpha server's IP, or coralnet.ucsd.edu. Regardless of that, it sends out email as coralnet.ucsd.edu because that's how the email system is configured. So there's no issue here.

    - Google maps. We currently don't use an API key here, but Google's recent API key enforcement includes a grandfathering policy for "existing applications". As for what that means, it's not quite clear. Here's the score so far:

      - Request host is coralnet.ucsd.edu, which resolves to the alpha server IP: Map works
      - Request host is alpha server's IP: Map works
      - Request host is staging server's IP: Map does not work
      - Request host is coralnet.ucsd.edu, which resolves to the staging server IP: ???

      If ??? ends up being "Map does not work", be prepared to take down the map in the alpha code, or quickly figure out how to plug an API key into the alpha code.

- Contact the UCSD hostmaster and/or CSEhelp: Tell them we want to have the coralnet.ucsd.edu domain switch to <our production elastic IP>.
- Announce downtime starting Friday-Saturday.

Phase 3

- Wait until Saturday or IP-switch-induced downtime.

- Take the alpha server down, using the first few steps of `this process <update_server_code>`__.
- Serve a simple "site is under maintenance" HTML response with nginx.

  - Do this on the staging server (which currently has the production elastic IP).
  - If coralnet.ucsd.edu still points to the old IP, also do this on the alpha server.

- :ref:`Sync files from the alpha server filesystem to the production S3 bucket <sync_filesystem_to_s3>`. This sync should just involve the new files since Phase 1. (2-3h waiting)
- :ref:`Migrate the alpha server database to the production RDS instance <beta_migration_database>`. (20m work, 40m waiting)
- :ref:`Update the code on the production EC2 instance <update_server_code>`.
- Since the database is in the alpha format again, :ref:`run all Django migrations <beta_migration_django_migrations>`. (20m work, 60m waiting)
- (Optional) :ref:`Reset production S3 file permissions to private <s3_reset_file_permissions>`. But if Phase 1 didn't come up with any non-private files, then we're probably fine here.
- Switch the production EC2 instance's Django settings to production.
- Run ``python manage.py makenginxconfig`` with production settings.
- Ensure all ``secrets.json`` details on the production EC2 instance are correct.
- Start running the vision backend on all existing sources.

Phase 4

- Wait until coralnet.ucsd.edu points to the production elastic IP.

  - Look for minor bugs to fix.
  - Review Django's security docs.

- Go to the AWS security group for the EC2 servers. Allow port 80 (HTTP) and 443 (HTTPS) access from only developers' IPs. This allows us to test the site without making it public yet.

- Switch the coralnet.ucsd.edu elastic IP from the server instance to the production instance.

- :ref:`Generate a TLS certificate <tls>` for coralnet.ucsd.edu.

  - Generating a new certificate seems safer than transferring the old certificate over the network from the alpha server. The old certificate's almost expired anyway.

- Update the S3 bucket policy's Referer line in light of the domain and scheme changes.

- :ref:`Add a Postfix email server <postfix>` (also secured with TLS) to the beta server. Test (being careful to not email any non-admins).

- Test the site.

  - Access with HTTP; confirm that it redirects to HTTPS.
  - Check that links on the site are HTTPS.
  - Check that going directly to an HTTPS URL works too.
  - Test signing in.
  - Check that media files are being served. For example, go to a Browse page.
  - Check that image patches can be generated. For example, go to a label-detail page.
  - Test email, using password-reset for example. Check that any links in the email use HTTPS and the correct domain.
  - Try at least one Ajax POST request. For example, supply a CSV to metadata-upload and see that the preview shows up.
  - Try an actual file upload. For example, do a metadata CSV upload (it doesn't actually have to change any metadata).
  - Ensure the vision backend is still running or available.
  - Check that Google Maps works.
  - Check that Gravatar-powered user profile images work.
  - Check that Google Analytics works.

- Go to the AWS security group for the EC2 servers. Allow port 80 (HTTP) and 443 (HTTPS) access from all IPs.

- Let users know that the site is back up, and point them to the "What's new in beta" guide.