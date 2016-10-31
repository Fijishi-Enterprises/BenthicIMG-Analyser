import posixpath
from django.conf import settings
from django.contrib.auth.models import User
from django.db import models
from django.utils.crypto import get_random_string

from easy_thumbnails.fields import ThumbnailerImageField


def get_avatar_upload_path(instance, filename):
    """
    Generate a destination path (on the server filesystem) for
    an upload of a profile avatar.
    """
    return settings.PROFILE_AVATAR_FILE_PATTERN.format(
        name=get_random_string(length=10),
        extension=posixpath.splitext(filename)[-1])


class Profile(models.Model):
    user = models.OneToOneField(
        User, unique=True,  on_delete=models.CASCADE, verbose_name="User")

    PRIVACY_CHOICES = (
        ('open', "Public"),
        ('registered', "Registered users only"),
        ('closed', "Private"),
    )
    privacy = models.CharField(
        "Privacy",
        max_length=15,
        choices=PRIVACY_CHOICES,
        default='registered',
        help_text="Designates who can view your profile.")

    AVATAR_WIDTH, AVATAR_HEIGHT = 80, 80
    mugshot = ThumbnailerImageField(
        "Avatar",
        blank=True,
        upload_to=get_avatar_upload_path,
        resize_source=dict(
            size=(AVATAR_WIDTH, AVATAR_HEIGHT), crop='smart'),
        help_text="Image to display in your profile.")

    @property
    def avatar(self):
        """Ease the process of renaming mugshot to avatar."""
        return self.mugshot

    about_me = models.CharField("About me", max_length=1000, blank=True)
    website = models.URLField("Website", blank=True)
    location = models.CharField("Location", max_length=45, blank=True)
