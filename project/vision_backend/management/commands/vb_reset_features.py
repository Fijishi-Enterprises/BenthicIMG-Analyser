from django.core.management.base import BaseCommand

from images.models import Image, Source
from ...utils import reset_features


class Command(BaseCommand):
    help = (
        "Reset features in batch. Note that vb_check_source can be"
        " used instead for images that don't have features yet."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            'mode', choices=['source_ids', 'image_ids'],
            help="Interpret following args as source or image IDs.")
        parser.add_argument(
            'ids', type=int, nargs='+',
            help="List of source/image IDs.")

    def handle(self, *args, **options):

        mode = options.get('mode')
            
        if mode == 'source_ids':
            for source_id in options['ids']:
                source = Source.objects.get(id=source_id)
                images = source.image_set.all()
                self.stdout.write(
                    f"Initiating feature resets for source"
                    f" {source_id} \"{source}\" ({images.count()} image(s))...")
                for image in images:
                    reset_features(image)
        else:
            # image_ids
            images = Image.objects.filter(pk__in=options['ids'])
            for image in images:
                self.stdout.write(
                    f"Initiating feature reset for image"
                    f" {image.pk}...")
                reset_features(image)

        self.stdout.write(
            "Done. Keep an eye out for the feature extraction jobs which"
            " should get queued and run.")
