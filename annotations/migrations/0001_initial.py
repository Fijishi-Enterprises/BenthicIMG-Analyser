# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import annotations.models
import easy_thumbnails.fields
from django.conf import settings
import django.core.validators


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Annotation',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('annotation_date', models.DateTimeField(auto_now=True)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='AnnotationToolAccess',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('access_date', models.DateTimeField(auto_now=True)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='AnnotationToolSettings',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('point_marker', models.CharField(default=b'crosshair', max_length=30, choices=[(b'crosshair', b'Crosshair'), (b'circle', b'Circle'), (b'crosshair and circle', b'Crosshair and circle'), (b'box', b'Box')])),
                ('point_marker_size', models.IntegerField(default=16, validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(30)])),
                ('point_marker_is_scaled', models.BooleanField(default=False)),
                ('point_number_size', models.IntegerField(default=24, validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(40)])),
                ('point_number_is_scaled', models.BooleanField(default=False)),
                ('unannotated_point_color', models.CharField(default=b'FFFF00', max_length=6, verbose_name=b'Not annotated point color')),
                ('robot_annotated_point_color', models.CharField(default=b'FFFF00', max_length=6, verbose_name=b'Unconfirmed point color')),
                ('human_annotated_point_color', models.CharField(default=b'8888FF', max_length=6, verbose_name=b'Conformed point color')),
                ('selected_point_color', models.CharField(default=b'00FF00', max_length=6)),
                ('show_machine_annotations', models.BooleanField(default=True)),
                ('user', models.ForeignKey(editable=False, to=settings.AUTH_USER_MODEL)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Label',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(max_length=45)),
                ('code', models.CharField(max_length=10, verbose_name=b'Short Code')),
                ('description', models.TextField(null=True)),
                ('thumbnail', easy_thumbnails.fields.ThumbnailerImageField(help_text=b"For best results, please use an image that's close to 150 x 150 pixels.\nOtherwise, we'll resize and crop your image to make sure it's that size.", upload_to=annotations.models.get_label_thumbnail_upload_path, null=True, verbose_name=b'Example image (thumbnail)')),
                ('create_date', models.DateTimeField(auto_now_add=True, verbose_name=b'Date created', null=True)),
                ('created_by', models.ForeignKey(editable=False, to=settings.AUTH_USER_MODEL, null=True, verbose_name=b'Created by')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='LabelGroup',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(max_length=45, blank=True)),
                ('code', models.CharField(max_length=10, blank=True)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='LabelSet',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('description', models.TextField(blank=True)),
                ('location', models.CharField(max_length=45, blank=True)),
                ('edit_date', models.DateTimeField(auto_now=True, verbose_name=b'Date edited')),
                ('labels', models.ManyToManyField(to='annotations.Label')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.AddField(
            model_name='label',
            name='group',
            field=models.ForeignKey(verbose_name=b'Functional Group', to='annotations.LabelGroup'),
            preserve_default=True,
        ),
    ]
