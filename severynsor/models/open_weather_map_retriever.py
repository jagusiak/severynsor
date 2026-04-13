import requests
from django.db import models
from django.utils import timezone
from .sensor_retriever import SensorRetriever
from .record import ValueRecord
from ..db_fields import EncryptedCharField

class OpenWeatherMapRetriever(SensorRetriever):
    api_key = EncryptedCharField(max_length=512)
    retriever_name = 'Open Weather Map'
    
    @classmethod
    def get_retriever_tile_html(cls):
        badges = cls.get_supported_types_badges()
        return f"""
        <div class="flex flex-col items-center p-6 bg-white dark:bg-base-900 rounded-xl shadow-sm border border-base-200 dark:border-base-800 hover:border-primary-500 transition-all cursor-pointer h-full">
            <h3 class="text-xl font-bold mb-3 text-gray-900 dark:text-gray-100">Open Weather Map</h3>
            <p class="text-sm text-gray-500 dark:text-gray-400 text-center mb-4 truncate w-full">Weather and air quality data.</p>
            <div class="mt-auto flex flex-wrap justify-center gap-1.5">
                {badges}
            </div>
        </div>
        """

    @property
    def measurement_type(self):
        from severynsor.constants import MeasureType
        mapping = {
            MeasureType.AQI: 'air_pollution.aqi',
            MeasureType.PM25: 'air_pollution.pm2_5',
            MeasureType.PM10: 'air_pollution.pm10',
            MeasureType.CO: 'air_pollution.co',
            MeasureType.NO2: 'air_pollution.no2',
            MeasureType.TEMPERATURE: 'weather.temp',
            MeasureType.HUMIDITY: 'weather.humidity',
            MeasureType.PRESSURE: 'weather.pressure',
            MeasureType.WIND_SPEED: 'weather.wind_speed',
        }
        actual_type = getattr(getattr(self, 'sensor', None), 'measure_type', None)
        if hasattr(self.sensor, 'valuesensor'):
            actual_type = self.sensor.valuesensor.measure_type
        return mapping.get(actual_type)

    @classmethod
    def get_supported_measure_types(cls):
        from severynsor.constants import MeasureType
        return [
            MeasureType.AQI,
            MeasureType.PM25,
            MeasureType.PM10,
            MeasureType.CO,
            MeasureType.NO2,
            MeasureType.TEMPERATURE,
            MeasureType.HUMIDITY,
            MeasureType.PRESSURE,
            MeasureType.WIND_SPEED,
        ]

    def grab_data(self):
        endpoint, key = self.measurement_type.split('.')
        url = f"https://api.openweathermap.org/data/2.5/{endpoint}?lat={self.sensor.location.latitude}&lon={self.sensor.location.longitude}&appid={self.api_key}"
        
        if endpoint == 'weather':
            url += "&units=metric"
            
        response = self.make_api_call(url)
        if response.status_code == 200:
            data = response.json()
            value = None
            if endpoint == 'air_pollution':
                items = data.get('list', [])
                if items:
                    item = items[0]
                    if key == 'aqi':
                        value = item.get('main', {}).get('aqi')
                    else:
                        value = item.get('components', {}).get(key)
            elif endpoint == 'weather':
                if key == 'wind_speed':
                    value = data.get('wind', {}).get('speed')
                else:
                    value = data.get('main', {}).get(key)
                    
            if value is not None:
                ValueRecord.objects.create(
                    sensor=self.sensor,
                    value=value,
                    timestamp=timezone.now()
                )
