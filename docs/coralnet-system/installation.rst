Installation of production/staging server
=========================================


#. Set up an AWS account and :doc:`IAM user authentication <topics/aws-auth>`.
#. Set up an :doc:`Amazon RDS instance <topics/aws-rds>`.
#. Set up an :doc:`S3 bucket <topics/aws-s3>`.
#. Set up an :doc:`Amazon EC2 instance with CoralNet installed on it <topics/aws-ec2>`.
#. Set up the :doc:`web server software <topics/web-server>`.
#. Set up the :doc:`vision backend <topics/vision-backend>`.
#. Add :ref:`server scripts <server-scripts>` to the EC2 instance for convenience, perhaps in ``/scripts``.
#. Visit the website and check various functionality. For example:

  - Access with HTTP; confirm that it redirects to HTTPS.
  - Check that links on the site are HTTPS.
  - Check that going directly to an HTTPS URL works too.
  - Test signing in.
  - Check that media files are being served. For example, go to a Browse page.
  - Check that image patches can be generated. For example, go to a label-detail page.
  - Test email, using password-reset for example. Check that any links in the email use HTTPS and the correct domain.
  - Try at least one Ajax POST request. For example, supply a CSV to metadata-upload and see that the preview shows up.
  - Try an actual file upload. For example, do a metadata CSV upload (it doesn't actually have to change any metadata).
  - Ensure the vision backend is available; check the ``backend_overview`` page.
  - Check that Google Maps works.
  - Check that Gravatar-powered user profile images work.
  - Check that Google Analytics works.
