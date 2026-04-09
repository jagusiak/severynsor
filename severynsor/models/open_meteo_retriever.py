import requests
from django.utils import timezone
from .sensor_retriever import SensorRetriever
from .record import ValueRecord

class OpenMeteoRetriever(SensorRetriever):
    retriever_name = 'Open meteo'
    
    @classmethod
    def get_retriever_tile_html(cls):
        badges = cls.get_supported_types_badges()
        return f"""
        <div class="flex flex-col items-center p-6 bg-white dark:bg-base-900 rounded-xl shadow-sm border border-base-200 dark:border-base-800 hover:border-primary-500 transition-all cursor-pointer h-full">
            <h3 class="text-xl font-bold mb-3 text-gray-900 dark:text-gray-100">Open Meteo</h3>
            <p class="text-sm text-gray-500 dark:text-gray-400 text-center mb-4 truncate w-full">Fetch weather data from Open-Meteo API.</p>
            <div class="mt-auto flex flex-wrap justify-center gap-1.5">
                {badges}
            </div>
        </div>
        """

    @property
    def current_type(self):
        from severynsor.constants import MeasureType
        mapping = {
            MeasureType.TEMPERATURE: 'temperature_2m',
            MeasureType.HUMIDITY: 'relative_humidity_2m',
            MeasureType.APPARENT_TEMPERATURE: 'apparent_temperature',
            MeasureType.PRECIPITATION: 'precipitation',
            MeasureType.WIND_SPEED: 'wind_speed_10m',
        }
        actual_type = getattr(getattr(self, 'sensor', None), 'measure_type', None)
        if hasattr(self.sensor, 'valuesensor'):
            actual_type = self.sensor.valuesensor.measure_type
        return mapping.get(actual_type)

    @classmethod
    def get_supported_measure_types(cls):
        from severynsor.constants import MeasureType
        return [
            MeasureType.TEMPERATURE,
            MeasureType.HUMIDITY,
            MeasureType.APPARENT_TEMPERATURE,
            MeasureType.PRECIPITATION,
            MeasureType.WIND_SPEED,
        ]

    def grab_data(self):
        url = f"https://api.open-meteo.com/v1/forecast?latitude={self.sensor.location.latitude}&longitude={self.sensor.location.longitude}&current={self.current_type}"
        response = self.make_api_call(url)
        if response.status_code == 200:
            data = response.json()
            value = data.get('current', {}).get(self.current_type)
            if value is not None:
                ValueRecord.objects.create(
                    sensor=self.sensor,
                    value=value,
                    timestamp=timezone.now()
                )
