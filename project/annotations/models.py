from django.contrib.auth.models import User
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from labels.models import Label


class Annotation(models.Model):
    annotation_date = models.DateTimeField(
        blank=True, auto_now=True, editable=False)
    point = models.ForeignKey('images.Point', on_delete=models.CASCADE,
        editable=False)
    image = models.ForeignKey('images.Image', on_delete=models.CASCADE,
        editable=False)

    # The user who made this annotation
    user = models.ForeignKey(User, on_delete=models.SET_NULL,
        editable=False, null=True)
    # Only fill this in if the user is the robot user
    robot_version = models.ForeignKey('vision_backend.Classifier', on_delete=models.SET_NULL,
        editable=False, null=True)

    label = models.ForeignKey(Label, on_delete=models.PROTECT)
    source = models.ForeignKey('images.Source', on_delete=models.CASCADE,
        editable=False)

    @property
    def label_code(self):
        # After labels.models refactor, change to
        # local_label = LocalLabel.objects.get(
        #     global_label=self.label, labelset=self.source.labelset)
        # return local_label.code
        return self.label.code

    def __unicode__(self):
        return "%s - %s - %s" % (
            self.image, self.point.point_number, self.label_code)


class AnnotationToolAccess(models.Model):
    access_date = models.DateTimeField(
        blank=True, auto_now=True, editable=False)
    image = models.ForeignKey('images.Image', on_delete=models.CASCADE,
        editable=False)
    source = models.ForeignKey('images.Source', on_delete=models.CASCADE,
        editable=False)
    user = models.ForeignKey(User, on_delete=models.SET_NULL,
        editable=False, null=True)


class AnnotationToolSettings(models.Model):

    user = models.ForeignKey(User, on_delete=models.CASCADE,
        editable=False)

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
