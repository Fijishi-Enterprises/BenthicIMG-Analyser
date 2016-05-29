import os
import posixpath
from django.conf import settings
from django.core.files.storage import FileSystemStorage, get_storage_class
from storages.backends.s3boto import S3BotoStorage

class MediaStorageS3(S3BotoStorage):
    """
    Location defaults to the S3 bucket's AWS_S3_MEDIA_SUBDIR directory.
    """
    def __init__(self, location=None, **kwargs):
        self.timezone = 'UTC'

        # It's tempting to put "location = getattr(settings, ...)" as
        # a class variable. But that risks obtaining the setting before a
        # unit test setup routine is able to change it. If we get the
        # setting in an __init__() method like this, then there's no
        # risk of getting the setting too early.
        if location is None:
            location = getattr(settings, 'AWS_S3_MEDIA_SUBDIR', None)
        kwargs['location'] = location
        super(MediaStorageS3, self).__init__(**kwargs)

    def path_join(self, *args):
        # For S3 paths, we join with forward slashes.
        return posixpath.join(*args)

class MediaStorageLocal(FileSystemStorage):
    """
    Location defaults to MEDIA_ROOT. That's what Django's
    default file storage class does.
    """
    def __init__(self, **kwargs):
        self.timezone = settings.TIME_ZONE
        super(MediaStorageLocal, self).__init__(**kwargs)

    def path_join(self, *args):
        # For local storage, we join paths depending on the OS rules.
        return os.path.join(*args)

class ProcessingStorageS3(S3BotoStorage):
    """
    Location defaults to the S3 bucket's AWS_S3_PROCESSING_SUBDIR directory.
    """
    def __init__(self, location=None, **kwargs):
        if location is None:
            location = getattr(settings, 'AWS_S3_PROCESSING_SUBDIR', None)
        kwargs['location'] = location
        super(ProcessingStorageS3, self).__init__(**kwargs)

class ProcessingStorageLocal(MediaStorageLocal):
    """
    Location defaults to PROCESSING_ROOT.
    """
    def __init__(self, location=None, **kwargs):
        if location is None:
            location = getattr(settings, 'PROCESSING_ROOT', None)
        kwargs['location'] = location
        super(ProcessingStorageLocal, self).__init__(**kwargs)

def get_processing_storage_class():
    return get_storage_class(settings.PROCESSING_DEFAULT_STORAGE)