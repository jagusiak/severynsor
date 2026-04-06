from django.db import models

class MeasureType(models.TextChoices):
    TEMPERATURE = 'temperature', 'Temperature'
    HUMIDITY = 'humidity', 'Humidity'
    PM25 = 'pm25', 'PM2.5'
    PM10 = 'pm10', 'PM10'
    CO = 'co', 'Carbon Monoxide (CO)'
    NO2 = 'no2', 'Nitrogen Dioxide (NO2)'
    PRESSURE = 'pressure', 'Pressure'
    WIND_SPEED = 'wind_speed', 'Wind Speed'
    AQI = 'aqi', 'Air Quality Index (AQI)'
    PRECIPITATION = 'precipitation', 'Precipitation'
    APPARENT_TEMPERATURE = 'apparent_temperature', 'Apparent Temperature'

MEASURE_UNITS = {
    MeasureType.TEMPERATURE: 'C',
    MeasureType.HUMIDITY: '%',
    MeasureType.PM25: 'µg/m³',
    MeasureType.PM10: 'µg/m³',
    MeasureType.CO: 'µg/m³',
    MeasureType.NO2: 'µg/m³',
    MeasureType.PRESSURE: 'hPa',
    MeasureType.WIND_SPEED: 'm/s',
    MeasureType.AQI: '',
    MeasureType.PRECIPITATION: 'mm',
    MeasureType.APPARENT_TEMPERATURE: 'C',
}
