from images.models import Source, Image, Point
from .models import Score

def print_image_scores(image_id):
	"""
	Print image scores to console. For debugging purposes.
	"""
	points = Point.objects.filter(image_id = image_id).order_by('id')
	for enu, point in enumerate(points):
		print '===', enu, point.row, point.column, '==='
		for score in Score.objects.filter(point = point):
			print score.label, score.score


def set_alleviate_to_zero():
	"""
	This scripts set the level of alleviation to 0 for all sources
	"""
    for source in Source.objects.filter(enable_robot_classifier=True):
        print "Processing source id:" + str(source.id)
        source.alleviate_threshold = 0
        source.save()			