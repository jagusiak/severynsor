from django.db import models
from django.apps import apps

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
