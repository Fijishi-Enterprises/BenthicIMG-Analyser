from django.urls import path

from . import views


app_name = 'calcification'

urlpatterns = [
    path('table_download/<int:table_id>/',
         views.rate_table_download,
         name='rate_table_download'),
]
