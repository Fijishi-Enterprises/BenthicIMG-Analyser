from argparse import RawTextHelpFormatter
import time

from django.core.management.base import BaseCommand

from images.models import Image
from jobs.tasks import run_scheduled_jobs
from lib.regtest_utils import VisionBackendRegressionTest
from ...models import Classifier
from ...tests.tasks.utils import queue_and_run_collect_spacer_jobs

reg_test_config = {
    372: {'small': (25, 5),
          'medium': (250, 30),
          'large': (1400, 50)},
    504: {'small': (25, 5),
          'medium': (100, 15),
          'large': (100, 15)}
}


class Command(BaseCommand):
    help = '''
        Run vision backend regression tests. Depending on your config
        you can run this reg-test in several modes:
        ## Local immediate
        This is the simplest setting. Local backend, sync tasks, local queue.
        ```
        HUEY_IMMEDIATE=True
        SPACER_QUEUE_CHOICE=vision_backend.queues.LocalQueue
        SETTINGS_BASE=dev-local
        ```
        
        ## Local async
        Here everything is still local, but jobs are executed asynchronously 
        using huey. Make sure the huey consumer is running before starting 
        the test: `python manage.py run_huey`.
        ```
        HUEY_IMMEDIATE=False
        SPACER_QUEUE_CHOICE=vision_backend.queues.LocalQueue
        SETTINGS_BASE=dev-local
        ```
        
        ## S3 async
        Still using the LocalQueue and async tasks, but storage is now on S3. 
        ```
        HUEY_IMMEDIATE=False
        SPACER_QUEUE_CHOICE=vision_backend.queues.LocalQueue
        SETTINGS_BASE=dev-s3
        ```
        ## AWS ECS cluster. 
        This uses the AWS Batch to process the jobs. 
        ```
        HUEY_IMMEDIATE=False
        SPACER_QUEUE_CHOICE=vision_backend.queues.BatchQueue
        SETTINGS_BASE=dev-s3
        ```
        
        Etc. etc. Most combinations work. The only requirement is that if you 
        use the `BatchQueue` you need to use the `dev-s3` setting. 
        
        NOTE: 
        If you use `dev-local` you still need to have AWS_ACCESS_KEY_ID and
        AWS_SECRET_ACCESS_KEY in your .env to allow access to fixtures and
        spacer models from s3.
        '''

    def create_parser(self, *args, **kwargs):
        """ This makes the help text more nicely formatted. """
        parser = super().create_parser(*args, **kwargs)
        parser.formatter_class = RawTextHelpFormatter
        return parser

    def add_arguments(self, parser):
        parser.add_argument(
            '--size',
            type=str,
            choices=['small', 'medium', 'large'],
            default='small',
            help='Choose size: '
                 'Small ~ 50 images; medium ~ 400 images; large ~ 1600 images')
        parser.add_argument(
            '--fixture_source',
            type=int,
            choices=[372, 504],
            default=372,
            help='Choose one of two sources to run your regression test on.')
        parser.add_argument(
            '--vgg16',
            action='store_true',
            help='Use VGG16 feature extractor instead of EfficientNet.')

    def handle(self, *args, **options):

        size = options['size']
        fixture_source_id = options['fixture_source']

        (n_with, n_without) = reg_test_config[fixture_source_id][size]

        s = VisionBackendRegressionTest(
            fixture_source_id, size.upper(), options['vgg16'])

        print("\n-> Uploading images which have manual annotations...")
        annotated_image_filepaths = s.upload_images(n_with)
        print("\n-> Adding manual annotations...")
        for image_filepath in annotated_image_filepaths:
            s.upload_anns(image_filepath)

        print("\n-> Uploading images which don't have manual annotations...")
        _ = s.upload_images(n_without)

        print("-> Waiting until feature extraction is done...")
        all_have_features = False
        while not all_have_features:
            time.sleep(5)
            run_scheduled_jobs()
            queue_and_run_collect_spacer_jobs()
            n_with_feats = Image.objects.filter(
                source=s.source, features__extracted=True).count()
            n_imgs = Image.objects.filter(source=s.source).count()
            print(f"-> {n_with_feats} out of {n_imgs} images have features.")
            all_have_features = n_with_feats == n_imgs

        print("-> All images have features!")

        print("-> Waiting until classifier training is done...")
        has_classifier = False
        while not has_classifier:
            time.sleep(5)
            run_scheduled_jobs()
            queue_and_run_collect_spacer_jobs()
            print("-> No classifier trained yet.")
            has_classifier = Classifier.objects.filter(
                source=s.source, status=Classifier.ACCEPTED).count() > 0

        print("-> Classifier trained!")

        print("-> Waiting for unconfirmed images to be classified.")
        all_imgs_classified = False
        while not all_imgs_classified:
            time.sleep(5)
            run_scheduled_jobs()
            n_classified = Image.objects.filter(
                source=s.source,
                annoinfo__confirmed=False,
                features__classified=True).count()
            n_imgs = Image.objects.filter(
                source=s.source,
                annoinfo__confirmed=False).count()

            print(
                f"-> {n_classified} out of {n_imgs} unconfirmed images"
                f" are classified.")
            all_imgs_classified = n_classified == n_imgs

        print("-> All Done!")
