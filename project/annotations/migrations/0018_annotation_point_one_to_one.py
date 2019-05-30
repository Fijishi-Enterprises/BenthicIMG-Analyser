# -*- coding: utf-8 -*-
# Generated by Django 1.9.11 on 2018-09-05 07:28
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('annotations', '0017_tool_settings_one_to_one'),
    ]

    operations = [
        migrations.AlterField(
            model_name='annotation',
            name='point',
            field=models.OneToOneField(editable=False, on_delete=django.db.models.deletion.CASCADE, to='images.Point'),
        ),
    ]