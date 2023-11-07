from django.core.exceptions import ValidationError

from lib.tests.utils import ClientTest
from ..models import ClassifyImageEvent, Event


class ModelSaveTest(ClientTest):

    def test_subclass_sets_type(self):
        user = self.create_user()
        source = self.create_source(user)
        image = self.upload_image(user, source)
        classifier = self.create_robot(source)

        classify_event = ClassifyImageEvent(
            source_id=source.pk,
            image_id=image.pk,
            classifier_id=classifier.pk,
            details={},
        )
        classify_event.save()
        classify_event.refresh_from_db()
        self.assertEqual(classify_event.type, 'classify_image')

    def test_subclass_required_fields(self):
        user = self.create_user()
        source = self.create_source(user)
        self.upload_image(user, source)
        classifier = self.create_robot(source)

        classify_event = ClassifyImageEvent(
            source_id=source.pk,
            classifier_id=classifier.pk,
            details={},
        )
        with self.assertRaises(ValidationError) as cm:
            classify_event.save()
        self.assertEqual(
            cm.exception.message,
            "This event type requires the image_id field.")


class ManagerTest(ClientTest):

    def test_queryset_default_filtering(self):
        user = self.create_user()
        source = self.create_source(user)
        image = self.upload_image(user, source)
        classifier = self.create_robot(source)

        event = Event(
            type='test',
            source_id=source.pk,
            details={},
        )
        event.save()
        classify_event = ClassifyImageEvent(
            source_id=source.pk,
            image_id=image.pk,
            classifier_id=classifier.pk,
            details={},
        )
        classify_event.save()

        # Set of all objects should filter by the event subclass's type,
        # if any.
        self.assertEqual(Event.objects.count(), 2)
        self.assertEqual(ClassifyImageEvent.objects.count(), 1)

        # get() should filter by the event subclass's type,
        # if any.
        with self.assertRaises(Event.MultipleObjectsReturned):
            Event.objects.get(source_id=source.pk)
        self.assertEqual(
            ClassifyImageEvent.objects.get(source_id=source.pk).pk,
            classify_event.pk,
        )
