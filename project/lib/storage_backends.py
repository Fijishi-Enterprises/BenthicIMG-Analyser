import os
import posixpath
from django.conf import settings
from django.core.files.storage import FileSystemStorage
from storages.backends.s3boto import S3BotoStorage

class MediaStorageS3(S3BotoStorage):
    location = getattr(settings, 'AWS_S3_MEDIA_SUBDIR', '')
    timezone = 'UTC'

    def path_join(self, *args):
        # Join with forward slashes
        return posixpath.join(*args)

class MediaStorageLocal(FileSystemStorage):
    timezone = settings.TIME_ZONE

    def path_join(self, *args):
        return os.path.join(*args)