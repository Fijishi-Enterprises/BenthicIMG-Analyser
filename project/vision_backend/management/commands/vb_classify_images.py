from django.core.management.base import BaseCommand

from images.models import Image, Source
from vision_backend.tasks import classify_image


class Command(BaseCommand):
    help = 'Classify all unclassified images in source. '

    def add_arguments(self, parser):

        parser.add_argument('--source_id', type=int, nargs='?', help="Source id to process")

    def handle(self, *args, **options):
        source = Source.objects.get(id=options['source_id'])

        for image in Image.objects.filter(source=source,
                                          features__extracted=True,
                                          features__classified=False,
                                          confirmed=False):
            classify_image.delay(image.id)
