from django.core.management.base import BaseCommand

from images.models import Point, Image
from annotations.models import Annotation
from annotations.utils import purge_annotations
from accounts.utils import get_robot_user


class Command(BaseCommand):
    help = 'Crawl DB to find points with multiple annotations. (Such points' \
           'should not exist, but due to a race condition problem, they do)'

    def add_arguments(self, parser):

        parser.add_argument('--dryrun', type=int, nargs=1, default=True, help="If true, don't take any action. "
                                                                               "Print findings only.")

    def handle(self, *args, **options):

        def status(image_id):
            robot_cnt, human_cnt = 0, 0
            for ann in Annotation.objects.filter(image_id=image_id):
                if ann.user == get_robot_user():
                    robot_cnt += 1
                else:
                    human_cnt += 1
            print('Image {} has {} points & {} anns: {} robot and {} human'.format(
                image_id, nbr_points, nbr_anns, robot_cnt, human_cnt))

        print("Crawling all images for duplicate annotations. dryrun={}".format(options['dryrun']))
        for image in Image.objects.filter():
            nbr_points = Point.objects.filter(image=image.pk).count()
            nbr_anns = Annotation.objects.filter(image=image.pk).count()
            if nbr_anns > nbr_points:
                status(image.id)
                if not options['dryrun']:
                    purge_annotations(image.id)
                    status(image.id)
