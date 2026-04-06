from django.db import models

class Location(models.Model):
    name = models.CharField(max_length=255)
    latitude = models.FloatField()
    longitude = models.FloatField()
    order = models.IntegerField(default=0)

    class Meta:
        ordering = ['order']


    def __str__(self):
        return self.name
