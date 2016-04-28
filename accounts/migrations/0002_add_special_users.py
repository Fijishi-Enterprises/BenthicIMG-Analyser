# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.conf import settings
from django.db import models, migrations


def add_special_users(apps, schema_editor):
    # We can't get the User model directly as it may be a newer
    # version than this migration expects. We use the historical version.
    #
    # Similarly, we can't use settings.AUTH_USER_MODEL as it may be
    # different from what this migration expects. So we specify auth.User.
    User = apps.get_model('auth', 'User')
    user = User(username=settings.IMPORTED_USERNAME)
    user.save()
    user = User(username=settings.ROBOT_USERNAME)
    user.save()
    user = User(username=settings.ALLEVIATE_USERNAME)
    user.save()

class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('accounts', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(add_special_users),
    ]
