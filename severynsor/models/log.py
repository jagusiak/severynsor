from django.db import models
from django.utils import timezone
from .sensor import Sensor
from .sensor_retriever import SensorRetriever

class ActivityLog(models.Model):
    RETRIEVER = 'retriever'
    API_CALL = 'api_call'
    
    TYPE_CHOICES = [
        (RETRIEVER, 'Retriever Execution'),
        (API_CALL, 'API Call'),
    ]

    type = models.CharField(max_length=20, choices=TYPE_CHOICES, default=RETRIEVER)
    sensor = models.ForeignKey(Sensor, on_delete=models.CASCADE, null=True, blank=True, related_name='activity_logs')
    retriever = models.ForeignKey(SensorRetriever, on_delete=models.CASCADE, null=True, blank=True, related_name='activity_logs')
    timestamp = models.DateTimeField(default=timezone.now)
    success = models.BooleanField(default=True)
    error_message = models.TextField(null=True, blank=True)
    
    # Context for API calls
    url = models.URLField(max_length=1000, null=True, blank=True)
    status_code = models.IntegerField(null=True, blank=True)
    duration = models.FloatField(help_text="Duration in seconds", null=True, blank=True)

    class Meta:
        ordering = ['-timestamp']
        verbose_name = 'Activity Log'
        verbose_name_plural = 'Activity Logs'

    def __str__(self):
        source = self.retriever.name if self.retriever and self.retriever.name else (self.sensor.title if self.sensor else "Unknown")
        return f"{self.get_type_display()} - {source} - {self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}"
