.. _git:

Git
=====


Setup
-----

Download and install Git, if you don't have it already.

Register an account on `Github <https://github.com/>`__ and ensure you have access to the coralnet repository.

Create an SSH key on your machine for your user profile, and add the public part of the key on your GitHub settings. See `instructions <https://help.github.com/articles/generating-a-new-ssh-key-and-adding-it-to-the-ssh-agent/>`__ on GitHub.

- This process could be optional for a local development machine, but it'll probably be required on the production server. If ``git`` commands result in a ``Permission Denied (publickey)`` error, then you know you have to complete this process. (`Source <https://gist.github.com/adamjohnson/5682757>`__)

- The ``-C`` option on the SSH key creation step doesn't have to be an email address. It's just a comment for you to remember what and who the SSH key is for. (`Source <http://serverfault.com/questions/309171/possible-to-change-email-address-in-keypair>`__)

Git-clone the coralnet repository to your machine.