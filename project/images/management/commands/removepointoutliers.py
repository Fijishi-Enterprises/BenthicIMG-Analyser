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

            f = open(options['file'], 'w')
            f.write(json.dumps(db))

        if options['mode'] == 'print':
            f = open(options['file'], 'r')
            db = json.loads(f.read())

            for image_pk in db.keys():
                print(image_pk, len(db[image_pk]))

        if options['mode'] == 'clean':
            f = open(options['file'], 'r')
            db = json.loads(f.read())

            for image_pk in db.keys():
                for point_pk in db[image_pk]:
                    point = Point.objects.get(pk = point_pk)
                    point.delete()



