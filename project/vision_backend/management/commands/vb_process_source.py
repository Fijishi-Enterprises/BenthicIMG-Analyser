from django.core.management.base import BaseCommand
from django.conf import settings

from images.models import Image, Source
from vision_backend.tasks import submit_features

class Command(BaseCommand):
    help = 'Process source completely.'

    def add_arguments(self, parser):

        parser.add_argument('mode', choices=['individual', 'parallel']) 
        parser.add_argument('--source_ids', type=int, nargs='+', help="list of source ids to process")
        parser.add_argument('--nbr_images', type=int, nargs=1, help="number of images per source")

    def handle(self, *args, **options):

        if options['mode'] == 'individual':
            assert options['source_ids']
            
            print "Running in individual mode"
            for source_id in options['source_ids']:
                source = Source.objects.get(id = source_id)
                images = Image.objects.filter(source = source, features__extracted=False)
                print "Submitting {} jobs for {}... ".format(images.count(), source.name)
                for image in images:
                    submit_features.delay(image.id)

        elif options['mode'] == 'parallel':
            assert options['nbr_images']
            nbr_images = options['nbr_images'][0]
            
            print "Running in parallel mode with {} images".format(nbr_images)
            for source in Source.objects.filter().order_by('-id'):
                images = Image.objects.filter(source = source, features__extracted=False)[:nbr_images]
                print "Submitting {} jobs for {}... ".format(images.count(), source.name)
                for image in images:
                    submit_features.delay(image.id)
