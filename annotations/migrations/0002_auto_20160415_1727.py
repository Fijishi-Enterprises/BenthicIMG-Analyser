# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
from django.conf import settings


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('annotations', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('images', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='annotationtoolaccess',
            name='image',
            field=models.ForeignKey(editable=False, to='images.Image'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='annotationtoolaccess',
            name='source',
            field=models.ForeignKey(editable=False, to='images.Source'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='annotationtoolaccess',
            name='user',
            field=models.ForeignKey(editable=False, to=settings.AUTH_USER_MODEL),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='annotation',
            name='image',
            field=models.ForeignKey(editable=False, to='images.Image'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='annotation',
            name='label',
            field=models.ForeignKey(to='annotations.Label'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='annotation',
            name='point',
            field=models.ForeignKey(editable=False, to='images.Point'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='annotation',
            name='robot_version',
            field=models.ForeignKey(editable=False, to='images.Robot', null=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='annotation',
            name='source',
            field=models.ForeignKey(editable=False, to='images.Source'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='annotation',
            name='user',
            field=models.ForeignKey(editable=False, to=settings.AUTH_USER_MODEL),
            preserve_default=True,
        ),
    ]
