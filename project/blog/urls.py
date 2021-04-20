from django.urls import path

from . import views


app_name = 'blog'

urlpatterns = [
    path('',
         views.PostsList.as_view(template_name='blog/post_list.html'),
         name='post_list'),
    path('<slug:slug>/',
         views.PostDetail.as_view(template_name='blog/post_detail.html'),
         name='post_detail'),
]
