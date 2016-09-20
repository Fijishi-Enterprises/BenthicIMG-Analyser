from images.models import Image, Point
from .models import Score

def print_image_scores(image_id):
	points = Point.objects.filter(image_id = image_id).order_by('id')
	for enu, point in enumerate(points):
		print '===', enu, point.row, point.column, '==='
		for score in Score.objects.filter(point = point):
			print score.label, score.score