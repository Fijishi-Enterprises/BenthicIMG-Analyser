from __future__ import unicode_literals
import six

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from reversion import revisions
from tqdm import tqdm

from accounts.utils import get_robot_user
from annotations.models import Annotation
from images.models import Source
from labels.models import Label

User = get_user_model()


class Command(BaseCommand):
    help = (
        "Replaces a source's confirmed annotations"
        " of old_label with new_label."
    )

    def add_arguments(self, parser):

        parser.add_argument(
            'source_id', type=int,
            help="ID of source you want to replace annotations in",
        )
        parser.add_argument(
            'old_label_id', type=int,
            help="ID of label whose annotations you want to replace",
        )
        parser.add_argument(
            'new_label_id', type=int,
            help="ID of label to change the annotations to",
        )
        parser.add_argument(
            'user_id', type=int,
            help="ID of user who will appear in annotation history entries",
        )

    def handle(self, *args, **options):

        source = Source.objects.get(pk=options['source_id'])
        source_label_ids = \
            source.labelset.get_globals().values_list('pk', flat=True)

        if options['old_label_id'] not in source_label_ids:
            raise ValueError(
                "The source's labelset doesn't have label ID {pk}.".format(
                    pk=options['old_label_id']))
        old_label = Label.objects.get(pk=options['old_label_id'])

        if options['new_label_id'] not in source_label_ids:
            raise ValueError(
                "The source's labelset doesn't have label ID {pk}.".format(
                    pk=options['new_label_id']))
        new_label = Label.objects.get(pk=options['new_label_id'])

        user = User.objects.get(pk=options['user_id'])
        robot_user = get_robot_user()

        annotations = Annotation.objects \
            .filter(point__image__source=source, label=old_label) \
            .exclude(user=robot_user)

        print("Source: {source_name}".format(source_name=source.name))
        print("{count} confirmed annotations of {label} found.".format(
            count=annotations.count(), label=old_label.name))
        print(
            "They will be changed to {label},".format(label=new_label.name)
            + " under the username {user}.".format(user=user.username))

        input_text = six.moves.input("OK? [y/N]: ")

        # Must input 'y' or 'Y' to proceed. Else, will abort.
        if input_text.lower() != 'y':
            print("Aborting.")
            return

        # Must explicitly turn on history creation when RevisionMiddleware is
        # not in effect. (It's only in effect within views.)
        with revisions.create_revision():
            for annotation in tqdm(annotations):
                annotation.label = new_label
                annotation.user = user
                annotation.save()
