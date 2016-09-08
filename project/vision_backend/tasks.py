import boto
import os
import json

from django.conf import settings
from images.models import Image, Point

from boto.sqs.message import Message

def features_extract(image_id):

    img = Image.objects.get(pk = image_id)
    rowcols = []
    
    for point in Point.objects.filter(image = img):
        rowcols.append((point.row, point.column))
    
    payload = {
        'bucketname': settings.AWS_STORAGE_BUCKET_NAME,
        'imkey': os.path.join(settings.AWS_S3_MEDIA_SUBDIR, img.original_file.name),
        'outputkey': os.path.join(settings.AWS_S3_MEDIA_SUBDIR, img.original_file.name, 'feats'),
        'modelname': 'vgg16_coralnet_ver1',
        'rowcols': rowcols
    }

    messagebody = {
    'task': 'extract_features',
    'payload': payload
    }

    conn = boto.sqs.connect_to_region("us-west-2",
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY)

    queue = conn.get_queue('spacer_jobs')
    m = Message()
    m.set_body(json.dumps(messagebody))
    queue.write(m)


