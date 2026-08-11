import asyncio
from asgiref.sync import async_to_sync
from django.db import models
from django.utils import timezone
from .sensor_retriever import SensorRetriever
from .record import ValueRecord
from ..db_fields import EncryptedCharField

class TapoRetriever(SensorRetriever):
    ip_address = models.GenericIPAddressField(help_text="IP Address of the Tapo Hub (e.g. H100)")
    username = models.CharField(max_length=255, help_text="Tapo account email")
    password = EncryptedCharField(max_length=512, help_text="Tapo account password")
    device_id = models.CharField(max_length=255, help_text="Device ID of the T310 or T315 sensor")

    retriever_name = 'Tapo Sensor'

    @classmethod
    def get_retriever_tile_html(cls):
        badges = cls.get_supported_types_badges()
        return f"""
        <div class="flex flex-col items-center p-6 bg-white dark:bg-base-900 rounded-xl shadow-sm border border-base-200 dark:border-base-800 hover:border-primary-500 transition-all cursor-pointer h-full">
            <h3 class="text-xl font-bold mb-3 text-gray-900 dark:text-gray-100">{cls.retriever_name}</h3>
            <p class="text-sm text-gray-500 dark:text-gray-400 text-center mb-4 truncate w-full">Read from Tapo T310/T315.</p>
            <div class="mt-auto flex flex-wrap justify-center gap-1.5">
                {badges}
            </div>
        </div>
        """

    @classmethod
    def get_supported_measure_types(cls):
        from severynsor.constants import MeasureType
        return [
            MeasureType.TEMPERATURE,
            MeasureType.HUMIDITY,
        ]

    def grab_data(self):
        async_to_sync(self.grab_data_async)()

    async def grab_data_async(self):
        from tapo import ApiClient
        
        client = ApiClient(self.username, self.password)
        hub = await client.h100(self.ip_address)
        child_device = await hub.child_device(self.device_id)
        
        records_obj = await child_device.get_temperature_humidity_records()
        
        # tapo-py returns an object with a `records` list
        records = getattr(records_obj, 'records', records_obj)
        
        if not records:
            return
            
        # Get the latest record
        def get_time(r):
            if hasattr(r, 'time'):
                return r.time
            elif isinstance(r, dict):
                return r.get('time', 0)
            return 0
            
        latest_record = sorted(records, key=get_time)[-1]
        
        actual_type = getattr(getattr(self, 'sensor', None), 'measure_type', None)
        if hasattr(self.sensor, 'valuesensor'):
            actual_type = self.sensor.valuesensor.measure_type
            
        from severynsor.constants import MeasureType
        value = None
        
        if actual_type == MeasureType.TEMPERATURE:
            if hasattr(latest_record, 'temp'):
                value = latest_record.temp
            elif isinstance(latest_record, dict):
                value = latest_record.get('temp')
        elif actual_type == MeasureType.HUMIDITY:
            if hasattr(latest_record, 'humidity'):
                value = latest_record.humidity
            elif isinstance(latest_record, dict):
                value = latest_record.get('humidity')
                
        if value is not None:
            ValueRecord.objects.create(
                sensor=self.sensor,
                value=value,
                timestamp=timezone.now()
            )
