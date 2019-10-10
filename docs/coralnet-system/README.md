# coralnet-system

This repository is for CoralNet parts which are specific to the production server setup.


## Cloning this repository

- Create an SSH key on your machine for your user profile, and add the public part of the key on your GitHub settings. See [instructions](https://help.github.com/articles/generating-a-new-ssh-key-and-adding-it-to-the-ssh-agent/) on GitHub.

  - This process may or may not be optional. If `git` commands result in a `Permission Denied (publickey)` error, then you know you have to complete this process. ([Source](https://gist.github.com/adamjohnson/5682757>))

  - The `-C` option on the SSH key creation step doesn't have to be an email address. It's just a comment for you to remember what and who the SSH key is for. ([Source](http://serverfault.com/questions/309171/possible-to-change-email-address-in-keypair>))

- Git-clone this coralnet repository to your machine.


## Building and viewing the documentation

- Make sure you have Python and Sphinx installed.
- Open a terminal/command line, cd to the `docs` directory of this repository, and run `make html`. (This command is cross platform, since there's a `Makefile` as well as a `make.bat`.)
- Open `docs/_build/html/index.html` in a web browser to start browsing the documentation.
- It's also possible to output in formats other than HTML, if you use `make <format>` with a different format. See [Sphinx's docs](http://www.sphinx-doc.org/en/master/usage/quickstart.html#running-the-build).
