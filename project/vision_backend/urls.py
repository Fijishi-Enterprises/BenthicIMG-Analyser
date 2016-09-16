from django.conf.urls import url
from . import views

urlpatterns = [
    url(r'^overview$', views.backend_overview, name="backend_overview"),
]
