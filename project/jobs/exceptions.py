class JobError(Exception):
    """
    Raise this during a Job to ensure the exception's caught by
    the code that cleans up after Jobs.
    """
    pass
