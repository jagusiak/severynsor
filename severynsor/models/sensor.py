import uuid
from PIL import Image
from django.db import models
from polymorphic.models import PolymorphicModel
from severynsor.constants import MeasureType

class Sensor(PolymorphicModel):
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to='severynsor/', blank=True, null=True)
    location = models.ForeignKey('severynsor.Location', on_delete=models.CASCADE)
    placement = models.CharField(max_length=255, blank=True, null=True)
    token = models.UUIDField(default=uuid.uuid4, unique=True)
    show_in_dashboard = models.BooleanField(default=True)
    
    @classmethod
    def get_model_tile_html(cls):
        return f"""
        <div class="flex flex-col items-center p-6 bg-white dark:bg-base-900 rounded-xl shadow-sm border border-base-200 dark:border-base-800 hover:border-primary-500 transition-all cursor-pointer h-full">
            <h3 class="text-xl font-bold mb-3 text-gray-900 dark:text-gray-100">{cls._meta.verbose_name.title()}</h3>
            <p class="text-sm text-gray-500 dark:text-gray-400 text-center">Generic sensor for tracking metadata.</p>
        </div>
        """

    class Meta:
        permissions = [
            ("can_view_token", "Can view and edit sensor token"),
            ("can_preview_sensor", "Can preview sensor data"),
        ]

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.image:
            img = Image.open(self.image.path)
            if img.height > 256 or img.width > 256:
                output_size = (256, 256)
                img.thumbnail(output_size)
                img.save(self.image.path)

    def __str__(self):
        return self.title

class ValueSensor(Sensor):
    measure_type = models.CharField(
        max_length=50,
        choices=MeasureType.choices,
        default=MeasureType.TEMPERATURE
    )
    
    class Meta:
        verbose_name = "Value"
        verbose_name_plural = "Value Sensors"

    @classmethod
    def get_model_tile_html(cls):
        return """
        <div class="flex flex-col items-center p-6 bg-white dark:bg-base-900 rounded-xl shadow-sm border border-base-200 dark:border-base-800 hover:border-primary-500 transition-all cursor-pointer h-full">
            <h3 class="text-xl font-bold mb-3 text-gray-900 dark:text-gray-100">Value Sensor</h3>
            <p class="text-sm text-gray-500 dark:text-gray-400 text-center mb-4">Measures numerical data over time.</p>
            <div class="mt-auto flex flex-wrap justify-center gap-1.5">
                <span class="px-2 py-0.5 rounded-md bg-base-100 dark:bg-base-800 text-[10px] uppercase font-bold text-gray-500 dark:text-gray-400 border border-base-200 dark:border-base-700">Open Meteo</span>
                <span class="px-2 py-0.5 rounded-md bg-base-100 dark:bg-base-800 text-[10px] uppercase font-bold text-gray-500 dark:text-gray-400 border border-base-200 dark:border-base-700">Open Weather Map</span>
            </div>
        </div>
        """

    def clean(self):
        super().clean()
        if self.pk:
            orig = ValueSensor.objects.get(pk=self.pk)
            if orig.measure_type != self.measure_type:
                if self.records.exists() or self.retrievers.exists():
                    from django.core.exceptions import ValidationError
                    raise ValidationError({"measure_type": "Cannot change measure type when records or retrievers are already connected to this sensor."})

    @property
    def measure_unit(self):
        from severynsor.constants import MEASURE_UNITS
        return MEASURE_UNITS.get(self.measure_type, '')

class ImageSensor(Sensor):
    @classmethod
    def get_model_tile_html(cls):
        return """
        <div class="flex flex-col items-center p-6 bg-white dark:bg-base-900 rounded-xl shadow-sm border border-base-200 dark:border-base-800 hover:border-primary-500 transition-all cursor-pointer h-full">
            <h3 class="text-xl font-bold mb-3 text-gray-900 dark:text-gray-100">Image Sensor</h3>
            <p class="text-sm text-gray-500 dark:text-gray-400 text-center mb-4">Captures and stores visual data.</p>
            <div class="mt-auto flex flex-wrap justify-center gap-1.5">
                <span class="px-2 py-0.5 rounded-md bg-base-100 dark:bg-base-800 text-[10px] uppercase font-bold text-gray-500 dark:text-gray-400 border border-base-200 dark:border-base-700">RTSP Stream</span>
            </div>
        </div>
        """

    class Meta:
        verbose_name = "Image"
        verbose_name_plural = "Image Sensors"
