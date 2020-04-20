from django.core.management.base import BaseCommand
from django.conf import settings

from images.models import Image, Point

import json

class Command(BaseCommand):
    help = 'Tool for submitting feature extraction across sources. '

    def add_arguments(self, parser):

        parser.add_argument('mode', choices=['scan', 'print', 'clean'], help = "") 
        parser.add_argument('file', type=str)

    def handle(self, *args, **options):


        if options['mode'] == 'scan':       
            db = dict()

            for image in Image.objects.filter():
                for point in Point.objects.filter(image=image):
                    if ((point.row > image.original_height) or (point.column > image.original_width)):
                        if not image.pk in db.keys():
                            db[image.pk] = []
                        db[image.pk].append(point.pk)

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
                    point = Point.objects.get(pk = point_pk)
                    point.delete()



