import posixpath
from django.conf import settings
from django.contrib.auth.models import User
from django.db import models
from easy_thumbnails.fields import ThumbnailerImageField
from lib.utils import rand_string


class LabelGroupManager(models.Manager):
    def get_by_natural_key(self, code):
        """
        Allow fixtures to refer to Label Groups by short code instead of by id.
        """
        return self.get(code=code)


class LabelGroup(models.Model):
    objects = LabelGroupManager()

    name = models.CharField(max_length=45, blank=True)
    code = models.CharField(max_length=10, blank=True)

    def __unicode__(self):
        """
        To-string method.
        """
        return self.name


def get_label_thumbnail_upload_path(instance, filename):
    """
    Generate a destination path (on the server filesystem) for
    an upload of a label's representative thumbnail image.
    """
    return settings.LABEL_THUMBNAIL_FILE_PATTERN.format(
        name=rand_string(10),
        extension=posixpath.splitext(filename)[-1])


class LabelManager(models.Manager):
    def get_by_natural_key(self, code):
        """
        Allow fixtures to refer to Labels by short code instead of by id.
        """
        return self.get(code=code)


class Label(models.Model):
    objects = LabelManager()

    name = models.CharField(max_length=45)
    code = models.CharField('Short Code', max_length=10)
    group = models.ForeignKey(
        LabelGroup, on_delete=models.PROTECT, verbose_name='Functional Group')
    description = models.TextField(null=True)

    # easy_thumbnails reference:
    # http://packages.python.org/easy-thumbnails/ref/processors.html
    THUMBNAIL_WIDTH, THUMBNAIL_HEIGHT = 150, 150
    thumbnail = ThumbnailerImageField(
        'Example image (thumbnail)',
        upload_to=get_label_thumbnail_upload_path,
        resize_source=dict(
            size=(THUMBNAIL_WIDTH, THUMBNAIL_HEIGHT), crop='smart'),
        help_text=(
            "For best results,"
            " please use an image that's close to {w} x {h} pixels."
            " Otherwise, we'll resize and crop your image"
            " to make sure it's that size.").format(
                w=THUMBNAIL_WIDTH, h=THUMBNAIL_HEIGHT),
        null=True,
    )

    create_date = models.DateTimeField(
        'Date created', auto_now_add=True, editable=False, null=True)
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL,
        verbose_name='Created by', editable=False, null=True)

    @property
    def global_label(self):
        # After labels.models refactor, ensure that all instances of
        # <Label obj>.global_label become
        # <LocalLabel obj>.global_label. Then remove this property.
        return self

    def __unicode__(self):
        """
        To-string method.
        """
        return self.name


class LabelSet(models.Model):
    # description and location are obsolete if we're staying with a 1-to-1
    # correspondence between labelsets and sources.
    description = models.TextField(blank=True)
    location = models.CharField(max_length=45, blank=True)
    labels = models.ManyToManyField(Label)
    edit_date = models.DateTimeField(
        'Date edited', auto_now=True, editable=False)

    def get_labels(self):
        # After labels.models refactor, replace this with:
        # return self.locallabel_set.all()
        return self.labels.all()

    def get_locals_ordered_by_group_and_code(self):
        # Must change 'group' to 'global_label__group'
        # after the labels.models refactor.
        return self.get_labels().order_by('group', 'code')

    def get_globals(self):
        # After labels.models refactor, replace this with:
        # global_label_ids = self.get_labels().values_list(
        #     'global_label__pk', flat=True)
        # return Label.objects.filter(pk__in=global_label_ids)
        return self.get_labels()

    def get_global_by_code(self, code):
        try:
            # Codes are case insensitive
            local_label = self.get_labels().get(code__iexact=code)
        # After labels.models refactor, change Label -> LocalLabel.
        except Label.DoesNotExist:
            return None
        return local_label.global_label

    def global_pk_to_code(self, global_pk):
        try:
            # After labels.models refactor,
            # change pk -> global_label__pk.
            local_label = self.get_labels().get(pk=global_pk)
        # After labels.models refactor, change Label -> LocalLabel.
        except Label.DoesNotExist:
            return None
        return local_label.code

    def __unicode__(self):
        source = self.source_set.first()
        if source:
            # Labelset of a source
            return "%s labelset" % source
        else:
            # Labelset that's not in any source (either a really old
            # labelset from early site development, or a labelset of a
            # deleted source which wasn't properly cleaned up)
            return "(Labelset not used in any source) " + self.description
