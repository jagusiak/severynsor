import base64
from django.core.files.base import ContentFile
from rest_framework import serializers
from .models import Record, ValueRecord, ImageRecord, ValueSensor, ImageSensor
from django.utils import timezone

class RecordSerializer(serializers.Serializer):
    value = serializers.FloatField(required=False)
    image = serializers.CharField(required=False, write_only=True)
    timestamp = serializers.DateTimeField(required=False)

    def create(self, validated_data):
        sensor = self.context['request'].auth
        timestamp = validated_data.get('timestamp', timezone.now())
        
        if isinstance(sensor, ValueSensor):
            if 'value' not in validated_data:
                raise serializers.ValidationError({"value": "This field is required for Value sensor."})
            return ValueRecord.objects.create(
                sensor=sensor,
                timestamp=timestamp,
                value=validated_data['value']
            )
        elif isinstance(sensor, ImageSensor):
            if 'image' not in validated_data:
                raise serializers.ValidationError({"image": "This field is required for Image sensor."})
            
            # decode base64
            image_data = validated_data['image']
            if ';base64,' in image_data:
                format, imgstr = image_data.split(';base64,')
                ext = format.split('/')[-1]
            else:
                imgstr = image_data
                ext = 'jpg'
            
            data = ContentFile(base64.b64decode(imgstr), name=f'api_upload_{sensor.id}_{timestamp.timestamp()}.{ext}')
            
            return ImageRecord.objects.create(
                sensor=sensor,
                timestamp=timestamp,
                image=data
            )
        else:
            raise serializers.ValidationError({"sensor": "Unsupported sensor type."})

    def to_representation(self, instance):
        if isinstance(instance, ValueRecord):
            return {
                'id': instance.id,
                'value': instance.value,
                'timestamp': instance.timestamp,
            }
        elif isinstance(instance, ImageRecord):
            return {
                'id': instance.id,
                'image': instance.image.url if instance.image else None,
                'timestamp': instance.timestamp,
            }
        return {}
