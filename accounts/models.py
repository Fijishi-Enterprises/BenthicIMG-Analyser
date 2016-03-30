from django.db import models
from django.utils.translation import ugettext_lazy as _

from userena.models import UserenaLanguageBaseProfile
from userena.models import User

class Profile(UserenaLanguageBaseProfile):
   user = models.OneToOneField(User, unique = True, verbose_name = _('user'),related_name = 'my_profile')
   about_me = models.CharField(_('Name'), max_length=45, blank=True)
   website = models.URLField(_('Website'), blank=True)
   location =  models.CharField(_('Location'), max_length=45, blank=True)
