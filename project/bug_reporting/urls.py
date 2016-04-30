from django.conf.urls import url
from . import views

urlpatterns = [
    url(r'$', views.feedback_form, name="feedback_form"),
]
