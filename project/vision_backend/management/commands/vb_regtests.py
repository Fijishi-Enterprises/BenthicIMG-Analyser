import logging
import time

from django.core.management.base import BaseCommand

from images.models import Image
from lib.regtest_utils import VisionBackendRegressionTest
from vision_backend.models import Classifier
from vision_backend.tasks import collect_all_jobs, submit_classifier

logging.disable(logging.CRITICAL)

reg_test_config = {
    372: {'small': (20, 5),
          'medium': (250, 30),
          'large': (1400, 50)},
    504: {'small': (20, 5),
          'medium': (100, 15),
          'large': (100, 15)}
}


class Command(BaseCommand):
    help = 'Run vision backend regression tests.'

    def add_arguments(self, parser):
        parser.add_argument('--size',
                            type=str,
                            choices=['small', 'medium', 'large'],
                            default='small',
                            help='Choose size: '
                                 'Small ~ 50 images; '
                                 'medium ~ 400 images; '
                                 'large ~ 1600 images')
        parser.add_argument('--fixture_source',
                            type=int,
                            choices=[372, 504],
                            default=372,
                            help='Choose one of two sources to run your '
                                 'regression test on.')

    def handle(self, *args, **options):

        size = options['size']
        fixture_source_id = options['fixture_source']

        (n_with, n_without) = reg_test_config[fixture_source_id][size]

        s = VisionBackendRegressionTest(fixture_source_id, size.upper())

        print("-> Uploading annotated images")
        s.upload_images(n_with, with_anns=True)

        print("-> Uploading un-annotated images")
        s.upload_images(n_without, with_anns=False)

        print("-> Waiting until feature extraction is done.")
        all_has_features = False
        while not all_has_features:
            time.sleep(3)
            collect_all_jobs()
            n_has_feats = Image.objects.filter(
                source=s.source, features__extracted=True).count()
            n_imgs = Image.objects.filter(source=s.source).count()
            print("-> {} out of images {} has features.".format(n_has_feats,
                                                                n_imgs))
            all_has_features = n_has_feats == n_imgs

        print("-> All images has features!")

        print("-> Submitting classifier for training.")
        submit_classifier.delay(s.source.id)
        has_classifier = False
        while not has_classifier:
            time.sleep(3)
            collect_all_jobs()
            print("-> No classifier trained yet.")
            has_classifier = Classifier.objects.filter(
                source=s.source, valid=True).count() > 0

        print("-> Classifier trained!")

        print("-> Waiting for unconfirmed images to be classified.")
        all_imgs_classified = False
        while not all_imgs_classified:
            time.sleep(3)
            collect_all_jobs()
            n_classified = Image.objects.filter(
                source=s.source, confirmed=False,
                features__classified=True).count()
            n_imgs = Image.objects.filter(source=s.source,
                                          confirmed=False).count()

            print("-> {} out of images {} are classified.".format(
                n_classified, n_imgs))
            all_imgs_classified = n_classified == n_imgs

        print("-> All Done!")
