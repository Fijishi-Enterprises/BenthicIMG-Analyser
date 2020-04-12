from __future__ import unicode_literals

from labels.models import Label
from lib.tests.utils import ManagementCommandTest


class ReplaceLabelInSourceTest(ManagementCommandTest):

    def test_basic(self):
        # Set up data
        user = self.create_user()
        source = self.create_source(user)
        labels = self.create_labels(user, ['A', 'B', 'C'], 'GroupA')
        self.create_labelset(user, source, labels)
        img = self.upload_image(user, source)
        self.add_annotations(
            user, img, {1: 'A', 2: 'B', 3: 'A', 4: 'C', 5: 'B', 6: 'C'})

        label_a = Label.objects.get(name='A')
        label_b = Label.objects.get(name='B')
        args = [source.pk, label_a.pk, label_b.pk, user.pk]
        stdout_text, _ = self.call_command_and_get_output(
            'annotations', 'replace_label_in_source', args=args,
            patch_input=True)

        # Verify output
        self.assertEqual(
            "Source: {}"
            "\n2 confirmed annotations of A found."
            "\nThey will be changed to B, under the username {}."
            "\nAlso, A will be removed from the labelset,"
            " and a source backend-reset will be initiated.".format(
                source.name, user.username),
            stdout_text)

        # Verify that A annotations were changed to B
        img.refresh_from_db()
        self.assertEqual(img.annotation_set.filter(label=label_a).count(), 0)
        self.assertEqual(img.annotation_set.filter(label=label_b).count(), 4)

        # Verify that A is no longer in the labelset
        source.refresh_from_db()
        self.assertListEqual(
            [label.name
             for label in source.labelset.get_globals_ordered_by_name()],
            ['B', 'C'])

    # TODO:
    # - Check that an annotation history entry was created.
    # - Test invalid parameter cases.
