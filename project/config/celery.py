from __future__ import absolute_import

import django

from celery import Celery
from django.conf import settings

django.setup()

app = Celery('coralnet')

app.config_from_object('django.conf:settings')
app.autodiscover_tasks(lambda: settings.INSTALLED_APPS)