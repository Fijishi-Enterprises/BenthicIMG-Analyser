import datetime

from django.contrib.auth.models import User
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone
from django.utils.encoding import python_2_unicode_compatible

from .managers import AnnotationManager
from images.models import Image, Point, Source
from labels.models import Label, LocalLabel
from vision_backend.models import Classifier


@python_2_unicode_compatible
class Annotation(models.Model):
    objects = AnnotationManager()

    annotation_date = models.DateTimeField(
        blank=True, auto_now=True, editable=False)
    point = models.OneToOneField(Point, on_delete=models.CASCADE, editable=False)
    image = models.ForeignKey(Image, on_delete=models.CASCADE, editable=False)

    # The user who made this annotation
    user = models.ForeignKey(User, on_delete=models.SET_NULL, editable=False, null=True)
    # Only fill this in if the user is the robot user
    robot_version = models.ForeignKey(Classifier, on_delete=models.SET_NULL, editable=False, null=True)

    label = models.ForeignKey(Label, on_delete=models.PROTECT)
    source = models.ForeignKey(Source, on_delete=models.CASCADE, editable=False)

    @property
    def label_code(self):
        local_label = LocalLabel.objects.get(
            global_label=self.label, labelset=self.source.labelset)
        return local_label.code

    def save(self, *args, **kwargs):
        super(Annotation, self).save(*args, **kwargs)
        # The image's annotation progress info may need updating.
        self.image.annoinfo.update_annotation_progress_fields()

    def delete(self, *args, **kwargs):
        super(Annotation, self).delete(*args, **kwargs)
        # The image's annotation progress info may need updating.
        self.image.annoinfo.update_annotation_progress_fields()

    def __str__(self):
        return u"%s - %s - %s" % (
            self.image, self.point.point_number, self.label_code)


class ImageAnnotationInfo(models.Model):
    """
    Annotation-related info for a single image.
    """
    image = models.OneToOneField(
        Image, on_delete=models.CASCADE, editable=False,
        # Name of reverse relation
        related_name='annoinfo')

    # Whether the image has confirmed annotations on all points. This is a
    # redundant field, in the sense that it can be computed from other fields.
    # But it's necessary for image-searching performance.
    confirmed = models.BooleanField(default=False)

    # Latest updated annotation for this image. This is a redundant field, in
    # the sense that it can be computed from other fields. But it's
    # necessary for performance of queries such as 'find the 20 most recently
    # annotated images'.
    last_annotation = models.ForeignKey(
        'annotations.Annotation', on_delete=models.SET_NULL,
        editable=False, null=True,
        # + means don't define a reverse relation. It wouldn't be helpful in
        # this case.
        related_name='+')

    def update_annotation_progress_fields(self):
        """
        Ensure the redundant annotation-progress fields (which exist for
        performance reasons) are up to date.
        """
        # Update the last_annotation.
        # If there are no annotations, then first() returns None.
        last_annotation = self.image.annotation_set.order_by(
            '-annotation_date').first()
        self.last_annotation = last_annotation

        # Must import within this function to avoid circular import
        # at the module level.
        from .utils import image_annotation_all_done
        # Are all points human annotated?
        all_done = image_annotation_all_done(self.image)

        # Update confirmed status, if needed.
        if self.confirmed != all_done:
            self.confirmed = all_done

            if self.confirmed:
                # With a new image confirmed, let's try to train a new
                # robot. The task will simply exit if there are not enough new
                # images or if a robot is already being trained.
                #
                # We have to import the task here, instead of at the top of the
                # module, to avoid circular import issues.
                from vision_backend.tasks import submit_classifier
                submit_classifier.apply_async(
                    args=[self.image.source.id],
                    eta=timezone.now()+datetime.timedelta(seconds=10))

        self.save()


class AnnotationToolAccess(models.Model):
    access_date = models.DateTimeField(
        blank=True, auto_now=True, editable=False)
    image = models.ForeignKey(Image, on_delete=models.CASCADE, editable=False)
    source = models.ForeignKey(Source, on_delete=models.CASCADE, editable=False)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, editable=False, null=True)


class AnnotationToolSettings(models.Model):

    user = models.OneToOneField(User, on_delete=models.CASCADE, editable=False)

    POINT_MARKER_CHOICES = (
        ('crosshair', 'Crosshair'),
        ('circle', 'Circle'),
        ('crosshair and circle', 'Crosshair and circle'),
        ('box', 'Box'),
        )
    MIN_POINT_MARKER_SIZE = 1
    MAX_POINT_MARKER_SIZE = 30
    MIN_POINT_NUMBER_SIZE = 1
    MAX_POINT_NUMBER_SIZE = 40

    point_marker = models.CharField(max_length=30, choices=POINT_MARKER_CHOICES, default='crosshair')
    point_marker_size = models.IntegerField(
        default=16,
        validators=[
            MinValueValidator(MIN_POINT_MARKER_SIZE),
            MaxValueValidator(MAX_POINT_MARKER_SIZE),
        ],
    )
    point_marker_is_scaled = models.BooleanField(default=False)

    point_number_size = models.IntegerField(
        default=24,
        validators=[
            MinValueValidator(MIN_POINT_NUMBER_SIZE),
            MaxValueValidator(MAX_POINT_NUMBER_SIZE),
        ],
    )
    point_number_is_scaled = models.BooleanField(default=False)

    unannotated_point_color = models.CharField(max_length=6, default='FFFF00', verbose_name='Not annotated point color')
    robot_annotated_point_color = models.CharField(max_length=6, default='FFFF00', verbose_name='Unconfirmed point color')
    human_annotated_point_color = models.CharField(max_length=6, default='8888FF', verbose_name='Confirmed point color')
    selected_point_color = models.CharField(max_length=6, default='00FF00')

    show_machine_annotations = models.BooleanField(default=True)


# TODO: Delete this function once migrations have been reset.
# Until then, this function must be kept so that old migrations
# don't trigger an error.
def get_label_thumbnail_upload_path(instance, filename):
    pass
