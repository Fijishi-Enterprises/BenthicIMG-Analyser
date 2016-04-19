from django.conf.urls import url
from . import views

urlpatterns = [
    url(r'^accounts/$', views.request_invite, name="request_account"),
    url(r'^accounts/confirm/$', views.request_invite_confirm, name="request_account_confirm"),
]