from django.db import models
from django.apps import apps
import re

def get_active_alarms_badge(request):
    if not request.user.is_authenticated:
        return None
    
    Alarm = apps.get_model('severynsor', 'Alarm')
    from django.utils import timezone
    now = timezone.now()
    
    count = Alarm.objects.filter(
        user=request.user, 
        state=True
    ).filter(
        models.Q(snooze_until__isnull=True) | models.Q(snooze_until__lte=now)
    ).count()
    
    return str(count) if count > 0 else ""

def get_media_size():
    import os
    from django.conf import settings
    total_size = 0
    start_path = settings.MEDIA_ROOT
    if not os.path.exists(start_path):
        return 0
    for dirpath, dirnames, filenames in os.walk(start_path):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            # skip if it is symbolic link
            if not os.path.islink(fp):
                total_size += os.path.getsize(fp)
    return total_size

def sanitize_text(text):
    if not text:
        return text
    
    # Sanitize RTSP URLs with credentials: rtsp://user:pass@host
    text = re.sub(r'(rtsp://)([^:]+):([^@]+)(@)', r'\1***:***\4', text)
    
    # Sanitize query parameters like appid, api_key, token
    text = re.sub(r'([?&](?:appid|api_key|token)=)([^&]+)', r'\1***', text)
    
    return text
