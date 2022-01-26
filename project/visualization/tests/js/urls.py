from django.urls import path
from . import views


app_name = 'visualization'

urlpatterns = [
    path('images_actions/',
         views.browse_images_actions,
         name="images_actions"),
]
