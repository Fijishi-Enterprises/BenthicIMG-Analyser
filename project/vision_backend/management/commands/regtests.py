import pickle
import json
import glob

import os.path as osp

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings

from lib.regtest_utils import RegressionTest


class Command(BaseCommand):
    help = 'Run vision backend regtests.'

    labelfile = osp.join(settings.REGRESSION_FIXTURES_ROOT, 'labels.json')

    def add_arguments(self, parser):
        parser.add_argument('scope', choices=['small', 'medium', 'large', 'huge'], help='Chose size of regtests. Small ~ 50 images; medium ~ 250 images; large ~ 1200 images; huge ~ 10000 images total.')

    def handle(self, *args, **options):
        scope = options['scope']
        if scope == 'small':
            # Only use a small fraction of each source
            for source_id in [372, 504]:
                s = RegressionTest(source_id, scope.upper())
                s.upload_images(20, with_anns = True)
                s.upload_images(5, with_anns = False)

        elif scope == 'medium':
            # Use 115 from each souce (which is all images for 504)
            for source_id in [372, 504]:
                s = RegressionTest(source_id, scope.upper())
                s.upload_images(100, with_anns = True)
                s.upload_images(15, with_anns = False)

        elif scope == 'large':
            # Use 1000 from 372
            s = RegressionTest(372, scope.upper())
            s.upload_images(1000, with_anns = True)
            s.upload_images(50, with_anns = False)

            s = RegressionTest(504, scope.upper())
            s.upload_images(100, with_anns = True)
            s.upload_images(15, with_anns = False)

        elif scope == 'huge':
            # Use all image from both sources
            s = RegressionTest(372, scope.upper())
            s.upload_images(9500, with_anns = True)
            s.upload_images(467, with_anns = False)

            s = RegressionTest(504, scope.upper())
            s.upload_images(100, with_anns = True)
            s.upload_images(15, with_anns = False)    
