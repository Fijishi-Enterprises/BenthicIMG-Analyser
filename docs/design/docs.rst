Documentation design notes
==========================


Names of .rst doc filenames and ref names
-----------------------------------------

Examples in other projects:

- `Sphinx <http://www.sphinx-doc.org/en/master/usage/restructuredtext/basics.html>`__ uses hyphens in both doc filenames (field-lists) and ref names (default-substitutions, rst-roles-alt).

- django-reversion uses hyphens in both doc filenames (`django-versions <https://github.com/etianen/django-reversion/tree/master/docs>`__), and ref names (`Revision-revert <https://raw.githubusercontent.com/etianen/django-reversion/master/docs/api.rst>`__).

- `Python dev guide <https://devguide.python.org/documenting/#cross-linking-markup>`__ uses no word separator in doc filenames (pullrequest), but hyphens in ref names (reporting-bugs, label-name).

- psycopg2 uses no word separator in doc filenames (`errorcodes <https://github.com/psycopg/psycopg2/blob/master/doc/src/errorcodes.rst>`__, but hyphens in ref names (`cursor-subclasses <https://raw.githubusercontent.com/psycopg/psycopg2/master/doc/src/advanced.rst>`__).

- boto uses hyphens in doc filenames (`ec2-example-key-pairs <https://github.com/boto/boto3/tree/develop/docs/source/guide>`__), but underscores in ref names (`guide_configuration, guide_resources <https://raw.githubusercontent.com/boto/boto3/develop/docs/source/guide/quickstart.rst>`__).

- The only explicitly stated convention found so far is hyphenated doc filenames in `OpenStack <https://docs.openstack.org/doc-contrib-guide/rst-conv/file-naming.html#file-naming-conventions>`__, cited as being for SEO.

The majority consensus for ``:ref:`` appears to be using hyphens for word separators.

The majority consensus for doc filenames appears to be: use hyphens for word separators, or have no word separator in some simple cases.


Section header punctuation characters in reStructuredText
---------------------------------------------------------

From the `Python Developer's Guide <https://devguide.python.org/documenting/#sections>`__:

  Normally, there are no heading levels assigned to certain characters as the structure is determined from the succession of headings.  However, for the Python documentation, here is a suggested convention:

  * ``#`` with overline, for parts
  * ``*`` with overline, for chapters
  * ``=``, for sections
  * ``-``, for subsections
  * ``^``, for subsubsections
  * ``"``, for paragraphs

The `style guide page itself <https://raw.githubusercontent.com/python/devguide/master/documenting.rst>`__ uses ``==`` with overline for the first heading in a document, then ``==`` without overline, then ``--`` and ``^^``. It's tough to find examples with ``""``, but presumably that would be the next level down.

Various other projects can be seen using ``==``, then ``--``, then ``^^``. Examples: `Pillow <https://raw.githubusercontent.com/python-pillow/Pillow/aaca672173413883fbcefd659f04d74fe44fb5d5/docs/installation.rst>`__, `django-reversion <https://raw.githubusercontent.com/etianen/django-reversion/master/docs/api.rst>`__, `psycopg2 <https://raw.githubusercontent.com/psycopg/psycopg2/master/doc/src/advanced.rst>`__.

There are also `boto <https://raw.githubusercontent.com/boto/boto3/develop/docs/source/guide/migration.rst>`__ and `Sphinx <http://www.sphinx-doc.org/en/master/_sources/usage/restructuredtext/basics.rst.txt>`__ which use ``==``, then ``--``, then ``~~``. (Despite this, the first convention Sphinx `actually mentions <http://www.sphinx-doc.org/en/master/usage/restructuredtext/basics.html#sections>`__ is the ``== -- ^^`` convention from the Python style guide.)

So far there haven't been examples of ``##`` or ``**``.

Overall, this doesn't matter much as long as we're fairly consistent. We might as well follow the Python dev guide's words and the majority, which appears to be ``== -- ^^`` (then perhaps ``""`` if needed).
