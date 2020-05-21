from collections import defaultdict
import json

from django.core.management.base import BaseCommand
from django.db.models import F

from images.models import Point


class Command(BaseCommand):
    help = 'Tool for submitting feature extraction across sources.'

    def add_arguments(self, parser):

        parser.add_argument('mode', choices=['scan', 'print', 'clean'], help="")
        parser.add_argument('file', type=str)

    def handle(self, *args, **options):

        if options['mode'] == 'scan':
            # Column too small OR too large OR row too small OR too large
            outlier_points = (
                Point.objects.filter(column__lt=0)
                | Point.objects.filter(column__gte=F('image__original_width'))
                | Point.objects.filter(row__lt=0)
                | Point.objects.filter(row__gte=F('image__original_height'))
            )

            db = defaultdict(list)

            for point in outlier_points:
                db[point.image.pk].append(point.pk)

            with open(options['file'], 'w') as f:
                f.write(json.dumps(db))

        if options['mode'] == 'print':
            with open(options['file'], 'r') as f:
                db = json.loads(f.read())

            for image_pk in db.keys():
                self.stdout.write('{} {}'.format(image_pk, len(db[image_pk])))

        if options['mode'] == 'clean':
            with open(options['file'], 'r') as f:
                db = json.loads(f.read())

            for image_pk in db.keys():
                for point_pk in db[image_pk]:
                    point = Point.objects.get(pk=point_pk)
                    point.delete()
