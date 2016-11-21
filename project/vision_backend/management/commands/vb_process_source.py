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
        parser.add_argument('--confirmed_only', type=int, default = 1, nargs = '?', help="only process confirmed images")

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
            confirmed_only = options['confirmed_only']

            print "Running in parallel mode with {} images and confirmed_only: {}".format(nbr_images, confirmed_only)
            for source in Source.objects.filter().order_by('-id'):
                if confirmed_only:
                    images = Image.objects.filter(source = source, confirmed = True, features__extracted=False)[:nbr_images]
                else:
                    images = Image.objects.filter(source = source, features__extracted=False)[:nbr_images]
                print "Submitting {} jobs for {}... ".format(images.count(), source.name)
                for image in images:
                    submit_features.delay(image.id)
