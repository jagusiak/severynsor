from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from severynsor.views import (
    value_sensor_preview,
    value_sensor_chart_data,
    image_sensor_preview,
    image_sensor_history_data,
    dashboard_settings,
    dashboard_settings_save,
    sensor_toggle_dashboard,
    sensor_toggle_dashboard,
    system_view,
    trigger_maintenance_task,
    download_backup,
)

urlpatterns = [
    path('system/', system_view, name='system_view'),
    path('api/', include(('severynsor.urls', 'severynsor-api'), namespace='severynsor-api')),
    # Preview URLs at top level so they don't conflict with admin
    path('severynsor/valuesensor/<int:object_id>/preview/',
         value_sensor_preview,
         name='severynsor_valuesensor_preview'),
    path('severynsor/imagesensor/<int:object_id>/preview/',
         image_sensor_preview,
         name='severynsor_imagesensor_preview'),
    path('severynsor/valuesensor/<int:object_id>/preview/chart-data/',
         value_sensor_chart_data,
         name='severynsor_valuesensor_chart_data'),
    path('severynsor/imagesensor/<int:object_id>/preview/history-data/',
         image_sensor_history_data,
         name='severynsor_imagesensor_history_data'),
    path('dashboard-settings/',
         dashboard_settings,
         name='dashboard_settings'),
    path('dashboard-settings/save/',
         dashboard_settings_save,
         name='dashboard_settings_save'),
    path('dashboard-settings/toggle-sensor/',
         sensor_toggle_dashboard,
         name='sensor_toggle_dashboard'),
    path('system/maintenance/', trigger_maintenance_task, name='trigger_maintenance_task'),
    path('system/backup/download/<str:filename>/', download_backup, name='download_backup'),
    path('', admin.site.urls),
]

if getattr(settings, 'DEBUG', False):
    urlpatterns = static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT) + urlpatterns
