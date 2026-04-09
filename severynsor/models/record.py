from django.db import models
from django.db.models.signals import post_delete
from django.dispatch import receiver
from polymorphic.models import PolymorphicModel
from .sensor import Sensor

class Record(PolymorphicModel):
    sensor = models.ForeignKey(Sensor, related_name='records', on_delete=models.CASCADE)
    timestamp = models.DateTimeField(db_index=True)

    def clean(self):
        super().clean()
        from django.core.exceptions import ValidationError
        from .sensor import ValueSensor, ImageSensor
        
        try:
            if self.pk:
                raise ValidationError("Existing records cannot be modified.")

            if isinstance(self, ValueRecord):
                if not isinstance(self.sensor, ValueSensor):
                    raise ValidationError({"sensor": "ValueRecord can only be assigned to a ValueSensor."})
                    
            if isinstance(self, ImageRecord):
                if not isinstance(self.sensor, ImageSensor):
                    raise ValidationError({"sensor": "ImageRecord can only be assigned to an ImageSensor."})
        except Sensor.DoesNotExist:
            pass

    def save(self, *args, **kwargs):
        if self.pk and not kwargs.get('force_insert', False):
            raise ValueError("Records cannot be edited once created.")
        super().save(*args, **kwargs)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.sensor.title} at {self.timestamp}"

    def display_value(self):
        return "-"

class ValueRecord(Record):
    value = models.FloatField()

    def __str__(self):
        return f"{self.sensor.title} - {self.value} at {self.timestamp}"

    def display_value(self):
        sensor = self.sensor
        # Accessing real instance properties if available
        unit = getattr(sensor, 'measure_unit', '')
        return f"{round(self.value, 2)} {unit}" if unit else f"{round(self.value, 2)}"

class ImageRecord(Record):
    image = models.ImageField(upload_to='records/', blank=True, null=True)

    def save(self, *args, **kwargs):
        is_new = self.pk is None or kwargs.get('force_insert', False)
        super().save(*args, **kwargs)
        if is_new and self.image and hasattr(self.image, 'path'):
            import subprocess
            try:
                # Run optimization on the saved file
                # --quiet: no output
                subprocess.run(['optimize-images', '--quiet', self.image.path], capture_output=True)
            except Exception:
                # Fail gracefully if optimization fails
                pass

    def __str__(self):
        return f"{self.sensor.title} - Image at {self.timestamp}"

    def display_value(self):
        if self.image:
            from django.utils.html import format_html
            return format_html('<img src="{}" style="width: 48px; height: 48px; border-radius: 4px; object-fit: cover;" />', self.image.url)
        return "-"

@receiver(post_delete, sender=ImageRecord)
def delete_image_file(sender, instance, **kwargs):
    """
    Deletes image file from filesystem when corresponding ImageRecord is deleted.
    """
    if instance.image:
        import os
        if os.path.isfile(instance.image.path):
            try:
                os.remove(instance.image.path)
            except Exception:
                pass
