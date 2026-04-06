import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from severynsor.models import Sensor
from rest_framework.test import APIClient
from django.utils import timezone

sensor = Sensor.objects.create(
    title="Test Sensor",
    description="A test sensor",
    location="Room 101",
    measure_unit="C"
)
print(f"Created Sensor with token: {sensor.token}")

client = APIClient()
client.credentials(HTTP_AUTHORIZATION=f'Bearer {sensor.token}')

response = client.post('/api/measurements/', {
    'value': 22.5,
    'timestamp': timezone.now().isoformat()
}, format='json')

print(response.status_code)
print(response.data)
