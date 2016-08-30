from django.conf.urls import url
from . import views

urlpatterns = [
    url(r'^metadata/$',
        views.export_metadata, name="export_metadata"),
]
