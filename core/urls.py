from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from severynsor.views import (
    value_sensor_preview,
    value_sensor_chart_data,
    image_sensor_preview,
    image_sensor_history_data,
)

urlpatterns = [
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
    path('', admin.site.urls),
]

if getattr(settings, 'DEBUG', False):
    urlpatterns = static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT) + urlpatterns
