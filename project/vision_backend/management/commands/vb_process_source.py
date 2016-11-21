from django.core.management.base import BaseCommand
from django.conf import settings

from images.models import Image, Source
from vision_backend.tasks import submit_features

class Command(BaseCommand):
    help = 'Process source completely.'

    def add_arguments(self, parser):
        parser.add_argument('source_ids', type=int, nargs='+', help="list of source ids to process")

    def handle(self, *args, **options):
        for source_id in options['source_ids']:
            source = Source.objects.get(id = source_id)
            images = Image.objects.filter(source = source, features__extracted=False)
            print "Submitting {} jobs for {}... ".format(images.count(), source.name)
            for image in images:
                submit_features.delay(image.id)
