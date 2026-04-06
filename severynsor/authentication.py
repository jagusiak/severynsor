from rest_framework import authentication
from rest_framework import exceptions
from .models import Sensor

class BearerSensorAuthentication(authentication.BaseAuthentication):
    def authenticate(self, request):
        auth = request.headers.get('Authorization')
        if not auth:
            return None

        try:
            scheme, token = auth.split()
            if scheme.lower() != 'bearer':
                return None
        except ValueError:
            return None

        try:
            sensor = Sensor.objects.get(token=token)
        except (Sensor.DoesNotExist, ValueError):
            raise exceptions.AuthenticationFailed('Invalid token.')

        return (None, sensor)
