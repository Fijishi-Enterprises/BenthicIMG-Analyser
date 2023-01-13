from .base_devserver import *

ALLOWED_HOSTS = ['127.0.0.1', 'testserver', 'localhost']

SPACER_QUEUE_CHOICE = 'vision_backend.queues.LocalQueue'
#SPACER_QUEUE_CHOICE = 'vision_backend.queues.BatchQueue'

# By default, huey runs tasks immediately if DEBUG is True, and doesn't if
# False. Can override that behavior here.
# HUEY['immediate'] = False

AWS_ACCESS_KEY_ID = get_secret('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = get_secret('AWS_SECRET_ACCESS_KEY')
os.environ['SPACER_AWS_ACCESS_KEY_ID'] = AWS_ACCESS_KEY_ID
os.environ['SPACER_AWS_SECRET_ACCESS_KEY'] = AWS_SECRET_ACCESS_KEY

# from .storage_s3 import *
from .storage_local import *
