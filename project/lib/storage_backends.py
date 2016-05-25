from django.conf import settings
from storages.backends.s3boto import S3BotoStorage

class MediaStorage(S3BotoStorage):
    location = settings.AWS_S3_MEDIA_SUBDIR