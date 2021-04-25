from django.urls import path
from . import views


urlpatterns = [
    path('<int:news_item_id>/', views.one_event, name="newsfeed_details"),
    path('', views.global_feed, name="newsfeed_global"),
]
