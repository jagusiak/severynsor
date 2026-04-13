import base64
import hashlib
from django.db import migrations
from django.conf import settings
from cryptography.fernet import Fernet

def encrypt_value(value):
    if not value:
        return value
    key = getattr(settings, 'FIELD_ENCRYPTION_KEY', settings.SECRET_KEY)
    h = hashlib.sha256(key.encode()).digest()
    fernet = Fernet(base64.urlsafe_b64encode(h))
    return fernet.encrypt(value.encode()).decode()

def migrate_data(apps, schema_editor):
    RTSPRetriever = apps.get_model('severynsor', 'RTSPRetriever')
    OpenWeatherMapRetriever = apps.get_model('severynsor', 'OpenWeatherMapRetriever')
    
    for obj in RTSPRetriever.objects.all():
        if obj.rtsp_url:
            obj.rtsp_url_new = encrypt_value(obj.rtsp_url)
            obj.save()
        
    for obj in OpenWeatherMapRetriever.objects.all():
        if obj.api_key:
            obj.api_key_new = encrypt_value(obj.api_key)
            obj.save()

def reverse_migrate_data(apps, schema_editor):
    # We don't really need to do anything here as the field will be deleted
    pass

class Migration(migrations.Migration):

    dependencies = [
        ('severynsor', '0025_add_temp_encrypted_fields'),
    ]

    operations = [
        migrations.RunPython(migrate_data, reverse_migrate_data),
    ]
