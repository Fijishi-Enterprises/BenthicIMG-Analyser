"""
This module contains scripts for manual testing.
"""

from .models import Image, Source, Metadata
from vision_backend.models import Features


def create_image(source_name):
	source = Source()
	source.name = source_name
	source.save()
	m = Metadata()
	m.name = 'a name goes here'
	m.save()
	feat = Features()
	feat.save()

	img = Image()
	img.name = 'Oscarimage'
	img.original_width = 10
	img.original_height = 10
	img.status = status
	img.source = source
	img.metadata = m
	img.features = feat
	img.save()
