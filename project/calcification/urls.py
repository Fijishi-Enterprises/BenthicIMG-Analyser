from django.urls import include, path

from . import views


app_name = 'calcification'

general_urlpatterns = [
    path('table_download/<int:table_id>/',
         views.rate_table_download,
         name='rate_table_download'),
]

source_urlpatterns = [
    path('stats_export/',
         views.CalcifyStatsExportView.as_view(),
         name='stats_export'),
]

urlpatterns = [
    path('calcification/', include(general_urlpatterns)),
    path('source/<int:source_id>/calcification/', include(source_urlpatterns)),
]
