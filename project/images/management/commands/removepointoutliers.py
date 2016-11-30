from django.core.management.base import BaseCommand
from django.conf import settings

from images.models import Image, Point

import json

class Command(BaseCommand):
    help = 'Tool for submitting feature extraction across sources. '

    def add_arguments(self, parser):

        parser.add_argument('dryrun', type=int, default = 1, nargs = '?', help="dryrun")
        parser.add_argument('outfile', type=str)

    def handle(self, *args, **options):

    	dryrun = options['dryrun']

        db = dict()

        for image in Image.objects.filter():
        	for point in Point.objects.filter(image=image):
        		if ((point.row > image.original_height) or (point.column > image.original_width)):
        			if not image.pk in db.keys():
        				db[image.pk] = []
        			db[image.pk].append(point.pk)

        f = open(options['outfile'], 'w')
        f.write(json.dumps(db))
        
        if dryrun:
        	for image_pk in db.keys():
        		image = Image.objects.get(pk = image_pk)
        		print '--' + image.name + '--'
        		for point_pk in db[image_pk]:
        			point = Point.objecs.get(pk = point_pk)
        			print point.row, point.column

