from django.urls import path
from . import views

urlpatterns = [
    path('', views.backend_main, name="backend_main"),
]
