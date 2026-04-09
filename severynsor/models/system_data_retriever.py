import shutil
from django.utils import timezone
from .sensor_retriever import SensorRetriever
from .record import ValueRecord

class SystemDataRetriever(SensorRetriever):
    retriever_name = 'System Data'
    
    @classmethod
    def get_retriever_tile_html(cls):
        badges = cls.get_supported_types_badges()
        return f"""
        <div class="flex flex-col items-center p-6 bg-white dark:bg-base-900 rounded-xl shadow-sm border border-base-200 dark:border-base-800 hover:border-primary-500 transition-all cursor-pointer h-full">
            <h3 class="text-xl font-bold mb-3 text-gray-900 dark:text-gray-100">System Data</h3>
            <p class="text-sm text-gray-500 dark:text-gray-400 text-center mb-4 truncate w-full">Fetch system stats like disk usage.</p>
            <div class="mt-auto flex flex-wrap justify-center gap-1.5">
                {badges}
            </div>
        </div>
        """

    @classmethod
    def get_supported_measure_types(cls):
        from severynsor.constants import MeasureType
        return [
            MeasureType.DISK_USED,
        ]

    def grab_data(self):
        from severynsor.constants import MeasureType
        
        actual_type = getattr(getattr(self, 'sensor', None), 'measure_type', None)
        if hasattr(self.sensor, 'valuesensor'):
            actual_type = self.sensor.valuesensor.measure_type
            
        if actual_type == MeasureType.DISK_USED:
            usage = shutil.disk_usage("/")
            percent = (usage.used / usage.total) * 100
            
            ValueRecord.objects.create(
                sensor=self.sensor,
                value=round(percent, 2),
                timestamp=timezone.now()
            )
