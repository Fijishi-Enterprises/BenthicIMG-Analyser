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


class FileStorageUsageError(Exception):
    """
    Raised upon incorrect/unsupported use of the file storage backend classes.
    """
    pass
