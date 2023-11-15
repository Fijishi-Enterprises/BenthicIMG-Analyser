# CoralNet

[![CI Status](https://github.com/coralnet/coralnet/actions/workflows/django.yml/badge.svg)](https://github.com/coralnet/coralnet/actions/workflows/django.yml)

CoralNet is a website which serves as a repository and resource for benthic image analysis.

Website home: https://coralnet.ucsd.edu

Read more about us: https://coralnet.ucsd.edu/about/

CoralNet's machine-learning processes are powered by PySpacer: https://github.com/coralnet/pyspacer


## Building and viewing the documentation

You can browse the docs right in the GitHub repo under `/docs`, but GitHub doesn't support some of the ReStructured Text links. The build will get everything working: 

- Download or `git clone` this repository's code.
- Install Python and Sphinx. You can do this by either following the installation steps (`docs/installation.rst` in this repo) until Sphinx is installed, or you can use some other Python environment which already has Sphinx installed.
- Open a terminal/command line, cd to the `docs` directory, and run `make html`. (This command is cross platform, since there's a ``Makefile`` as well as a ``make.bat``.)
- Open `docs/_build/html/index.html` in a web browser to start browsing the documentation.
- It's also possible to output in formats other than HTML, if you use ``make <format>`` with a different format. See [Sphinx's docs](http://www.sphinx-doc.org/en/master/usage/quickstart.html#running-the-build).
