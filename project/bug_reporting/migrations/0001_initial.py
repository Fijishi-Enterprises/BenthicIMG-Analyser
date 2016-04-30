# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
from django.conf import settings


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Feedback',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('type', models.CharField(max_length=1, choices=[(b'b', b'Bug Report'), (b'r', b'Suggestion / Request'), (b'f', b'Feedback / Other')])),
                ('comment', models.TextField(verbose_name=b'Description / Comment')),
                ('date', models.DateTimeField(auto_now_add=True, verbose_name=b'Date')),
                ('url', models.TextField(verbose_name=b'Url')),
                ('error_id', models.CharField(max_length=100, editable=False, blank=True)),
                ('user', models.ForeignKey(to=settings.AUTH_USER_MODEL)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
    ]
