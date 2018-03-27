from django.core.management.base import BaseCommand

from images.models import Image, Source
import os

from django.conf import settings
import boto


class Command(BaseCommand):
    help = 'Tool for submitting feature extraction across sources. '

    def add_arguments(self, parser):

        parser.add_argument('source_id', type=int, nargs='?', help="Source to export")
        parser.add_argument('--nbr_images', type=int, nargs='?', default=10, help="Max number of images to process")
        parser.add_argument('--bucket', type=str, help="bucket name to export to")

    def handle(self, *args, **options):

        source = Source.objects.get(id=options['source_id'])

        for img in Image.objects.filter(source=source)[:options['nbr_images']]:

            full_image_path = os.path.join(settings.AWS_LOCATION, img.original_file.name)
            from_name = settings.FEATURE_VECTOR_FILE_PATTERN.format(full_image_path=full_image_path)
            to_name = img.metadata.name
            print(from_name, to_name)
            c = boto.connect_s3(settings.AWS_ACCESS_KEY_ID,
                                  settings.AWS_SECRET_ACCESS_KEY)

            dst = c.get_bucket(options['bucket'])
            print(src, dst)

            dst.copy_key(to_name, settings.AWS_STORAGE_BUCKET_NAME, from_name)
