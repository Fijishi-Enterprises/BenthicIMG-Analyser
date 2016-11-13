.. _aws:

Amazon Web Services
===================

This page contains setup procedures for miscellaneous components of Amazon Web Services (AWS).


IAM user setup
--------------

- *Production/staging server*
- *Development server with S3 media storage*

The project only has one AWS root account, but it can have multiple IAM users - for example, one IAM user per team member.

Each IAM user has their own login credentials, and each IAM user can have specific permissions applied to them, rather than having access to everything about the AWS account. Using IAM should be more secure than having everyone log in to the AWS root account regularly.

First, log into your AWS root account and go to the Amazon IAM dashboard.

Create an IAM user. See `this Amazon docs page <http://docs.aws.amazon.com/AWSEC2/latest/UserGuide/get-set-up-for-amazon-ec2.html#create-an-iam-user>`__ for details.

Now you can log into AWS using your IAM user credentials, rather than your AWS root account credentials. The IAM login page can be found at `https://<12 digit account number>.signin.aws.amazon.com/console/`. You should also see the page if you visit one of the AWS console pages after not logging in for a while.


.. _aws_key_pair:

Key pair
--------

An AWS key pair allows you to authenticate to an EC2 instance with public-key cryptography instead of a password.

See `this Amazon docs page <http://docs.aws.amazon.com/AWSEC2/latest/UserGuide/get-set-up-for-amazon-ec2.html#create-a-key-pair>`__ for details on creating and configuring a key pair.