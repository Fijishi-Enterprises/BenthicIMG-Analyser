import hashlib
import posixpath
import uuid
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


def get_random_gravatar_hash():
    # Get a random md5 hash and format as a hex string.
    # http://stackoverflow.com/a/20060712/
    return uuid.uuid4().hex


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

    AVATAR_SIZE = 80
    avatar_file = ThumbnailerImageField(
        "Avatar file",
        blank=True,
        upload_to=get_avatar_upload_path,
        resize_source=dict(
            size=(AVATAR_SIZE, AVATAR_SIZE), crop='smart'),
        help_text="Upload an image to display in your profile.")

    use_email_gravatar = models.BooleanField(
        "Use a Gravatar based on my email address",
        default=False,
        help_text=(
            "If you're not sure what Gravatar is,"
            " just leave this unchecked."))

    random_gravatar_hash = models.CharField(
        "Random Gravatar hash",
        max_length=32,
        blank=False,
        default=get_random_gravatar_hash,
        editable=False,
        help_text=(
            "If an avatar isn't specified in another way, the fallback is a"
            " Gravatar based on this hash."))

    affiliation = models.CharField(
        "Affiliation", max_length=100, blank=True,
        help_text="Your university, research institution, etc.")

    about_me = models.CharField("About me", max_length=1000, blank=True)
    website = models.URLField("Website", blank=True)
    location = models.CharField("Location", max_length=45, blank=True)

    reason_for_registering = models.CharField(
        "Reason for registering", max_length=500, blank=True)
    project_description = models.CharField(
        "Project description", max_length=500, blank=True)
    how_did_you_hear_about_us = models.CharField(
        "How did you hear about us?", max_length=500, blank=True)

    @classmethod
    def _get_gravatar_url(cls, hash):
        # In general, we don't have the request object handy, so we can't use
        # request.scheme. This is the next best thing that comes to mind.
        if settings.SESSION_COOKIE_SECURE:
            scheme = 'https'
        else:
            scheme = 'http'

        fmt = '{scheme}://www.gravatar.com/avatar/{hash}?d=identicon&s={size}'
        return fmt.format(scheme=scheme, hash=hash, size=cls.AVATAR_SIZE)

    def get_avatar_url(self):
        if self.use_email_gravatar:
            # User chose to use an email-based gravatar
            return self._get_gravatar_url(
                hashlib.md5(self.user.email.lower()).hexdigest())
        if self.avatar_file:
            # User provided an uploaded image
            return posixpath.join(settings.MEDIA_URL, self.avatar_file.name)
        # Fall back to a random gravatar
        return self._get_gravatar_url(self.random_gravatar_hash)
