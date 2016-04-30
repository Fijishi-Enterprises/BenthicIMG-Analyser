Installation
============


Git
-----
Download and install Git, if you don't have it already.

Register an account on `Github <https://github.com/>`_ and ensure you have access to the coralnet repository.

Git-clone the coralnet repository to your machine.


PostgreSQL
----------
TODO


Python
------
Download and install Python 2.7.11. 32 bit or 64 bit doesn't matter. It's perfectly fine to keep other Python versions on the same system. Just make sure that your ``python`` and ``pip`` commands point to the correct Python version.

Upgrade pip: ``python -m pip install -U pip``


Virtualenv
----------
Install virtualenv: ``pip install virtualenv``

Create a virtual environment as described in the `Virtualenv docs <https://virtualenv.pypa.io/en/latest/userguide.html>`_.

You should ensure that your virtual environment is activated when installing Python packages or running Django management commands for the CoralNet project. From here on out, these instructions will assume you have your virtual environment (also referred to as virtualenv) activated.


Python packages
---------------
Look under ``requirements`` in the coralnet repository. If you are setting up a development machine, you want to use ``requirements/local.txt``. If you are setting up the production machine, you want to use ``requirements/production.txt``.

With your virtualenv activated, run ``pip install -r requirements/<name>.txt``.


Django settings
---------------
TODO


Django migrations
-----------------
TODO


secrets.json
------------
TODO


maintenance_notice.html
-----------------------
TODO


Sphinx docs
-----------
Not exactly an installation step, but here's how to build the docs for offline viewing. This can be especially useful when editing the docs.

Go into the ``docs`` directory and run: ``make html``. (This command is cross platform, since there's a ``Makefile`` as well as a ``make.bat``.)

Then you can browse the documentation starting at ``docs/_build/html/index.html``.

It's also possible to output in formats other than HTML, if you use ``make <format>`` with a different format.