"""
Extra exception types that may be thrown in CoralNet methods.
These can be useful if:

- When catching exceptions that you've thrown, you don't want
to catch any exceptions that you didn't anticipate.  For example, perhaps
you were going to throw and catch a ValueError in some case, but you're
worried that you'll accidentally catch a ValueError from some other error
case that you didn't think of.

- You want the types of exceptions to better describe the nature of the
exception, for more self-documenting code.  (It's advised to not go
overboard and create tons of exception types, though.)
"""

class FileProcessError(Exception):
    """
    When file contents are not as expected; either the wrong format or can't
    be matched to something in the database. For example, a line in a text
    file doesn't have the expected number of words, or one of the words
    in the file is supposed to match something in the database but doesn't.

    Contrast this with IOError, which is for problems with finding a file,
    not being able to read the file format, etc.
    """
    pass

class DirectoryAccessError(Exception):
    """
    Raised when a directory is expected to exist, be readable, and/or be
    writable, and that turns out to not be the case.
    For example, a directory is specified in a settings file and
    we now want to create a file in that directory, but that directory
    doesn't exist.
    """
    pass

class TestfileDirectoryError(Exception):
    """
    When there's something wrong with a directory meant to hold
    temporary test-generated files:
    (1) The directory already has files in it before a test.
    (2) After the test, the directory has a file that was created
        before the test began. (Given (1), this is a serious corner
        case, but still, we do not want to take chances with file
        deletions.)
    """
    pass