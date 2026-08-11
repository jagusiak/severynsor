import datetime
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from polymorphic.models import PolymorphicModel
from .sensor import Sensor

class SensorRetriever(PolymorphicModel):
    name = models.CharField(max_length=255, blank=True, null=True, unique=True, help_text="Optional custom name for this retriever")
    sensor = models.ForeignKey(Sensor, related_name='retrievers', on_delete=models.CASCADE)
    frequency_minutes = models.PositiveIntegerField(default=1, help_text="Frequency in minutes (min 1)")
    enabled = models.BooleanField(default=True)
    
    retriever_name = 'Base Retriever'
    
    @classmethod
    def get_supported_types_badges(cls):
        from severynsor.constants import MeasureType
        
        # This is a bit hacky because we don't have instances here
        # but the methods are hardcoded lists anyway
        if hasattr(cls, 'get_supported_measure_types'):
            supported = cls.get_supported_measure_types()
            labels = [dict(MeasureType.choices)[t] for t in supported]
            badges = "".join([f'<span class="px-2 py-0.5 rounded-md bg-base-100 dark:bg-base-800 text-[10px] uppercase font-bold text-gray-500 dark:text-gray-400 border border-base-200 dark:border-base-700">{l}</span>' for l in labels])
            return badges
        return ""

    @classmethod
    def get_retriever_tile_html(cls):
        return f"""
        <div class="flex flex-col items-center p-6 bg-white dark:bg-base-900 rounded-xl shadow-sm border border-base-200 dark:border-base-800 hover:border-primary-500 transition-all cursor-pointer h-full">
            <h3 class="text-xl font-bold mb-3 text-gray-900 dark:text-gray-100">{cls.retriever_name}</h3>
            <p class="text-sm text-gray-500 dark:text-gray-400 text-center mb-4">Base retriever for severynsor.</p>
        </div>
        """

    def clean(self):
        super().clean()
        from .open_meteo_retriever import OpenMeteoRetriever
        from .open_weather_map_retriever import OpenWeatherMapRetriever
        from .rtsp_retriever import RTSPRetriever
        from .system_data_retriever import SystemDataRetriever
        from .tapo_retriever import TapoRetriever
        from .sensor import ValueSensor, ImageSensor

        try:
            if self.pk:
                orig = SensorRetriever.objects.get(pk=self.pk)
                if orig.sensor_id != self.sensor_id:
                    raise ValidationError({"sensor": "Cannot change the sensor once the retriever is created."})

            if isinstance(self, (OpenMeteoRetriever, OpenWeatherMapRetriever, SystemDataRetriever, TapoRetriever)):
                if not isinstance(self.sensor, ValueSensor):
                    raise ValidationError({"sensor": "Value-based retriever can only be assigned to a ValueSensor."})
                
                if hasattr(self.sensor, 'valuesensor'):
                    actual_type = self.sensor.valuesensor.measure_type
                else:
                    actual_type = self.sensor.measure_type
                
                supported_types = self.get_supported_measure_types()
                if actual_type not in supported_types:
                    raise ValidationError({"sensor": f"Sensor measure type '{actual_type}' is not supported by {self.retriever_name}. Supported types: {', '.join(supported_types)}."})
                    
            if isinstance(self, RTSPRetriever):
                if not isinstance(self.sensor, ImageSensor):
                    raise ValidationError({"sensor": "Image-based retriever can only be assigned to an ImageSensor."})
        except Sensor.DoesNotExist:
            pass

    def should_run(self):
        if not self.enabled:
            return False
            
        now = timezone.now()
        timestamp = now.timestamp()
        
        period_duration = self.frequency_minutes * 60
        current_period_start = (timestamp // period_duration) * period_duration
        current_period_end = current_period_start + period_duration
        
        start_dt = datetime.datetime.fromtimestamp(current_period_start, tz=datetime.timezone.utc)
        end_dt = datetime.datetime.fromtimestamp(current_period_end, tz=datetime.timezone.utc)
        
        return not self.sensor.records.filter(
            timestamp__gte=start_dt,
            timestamp__lt=end_dt
        ).exists()

    def grab_data(self):
        raise NotImplementedError

    def make_api_call(self, url, method='GET', **kwargs):
        import requests
        try:
            response = requests.request(method, url, **kwargs)
            return response
        except Exception as e:
            raise e

    def __str__(self):
        if self.name:
            return self.name
        return f"{self.sensor.title} Retriever ({self.frequency_minutes}m)"
