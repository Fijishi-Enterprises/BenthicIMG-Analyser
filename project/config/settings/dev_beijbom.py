from .base_devserver import *

ALLOWED_HOSTS = ['127.0.0.1', 'testserver']

# SPACER_QUEUE_CHOICE = 'vision_backend.queues.SQSQueue'
# from .storage_s3 import *
from .storage_local import *

