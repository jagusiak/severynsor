from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from .sensor import Sensor
from django.contrib.auth.models import User
from severynsor.logic.conditions import Condition

class Alarm(models.Model):
    title = models.CharField(max_length=255)
    sensor = models.ForeignKey(Sensor, related_name='alarms', on_delete=models.CASCADE)
    user = models.ForeignKey(User, related_name='alarms', on_delete=models.CASCADE)
    state = models.BooleanField(default=False)
    last_change = models.DateTimeField(auto_now_add=True)
    conditions = models.JSONField(default=dict)
    
    send_email_when_on = models.BooleanField(default=False)
    send_email_when_off = models.BooleanField(default=False)
    snooze_until = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        verbose_name = "Alarm"
        verbose_name_plural = "Alarms"

    def __str__(self):
        return f"{self.title} ({'ON' if self.state else 'OFF'})"

    def get_evaluated_state(self):
        if not self.conditions:
            return self.state
        
        try:
            cond_obj = Condition.from_dict(self.conditions)
            return bool(cond_obj.eval(self.sensor))
        except Exception as e:
            print(f"Error evaluating alarm: {e}")
            return self.state

    def save(self, *args, **kwargs):
        # Detect state changes to update last_change
        old_state = None
        if self.pk:
            try:
                old_state = Alarm.objects.get(pk=self.pk).state
            except Alarm.DoesNotExist:
                pass

        # Re-evaluate state on save if conditions or sensor might have changed
        update_fields = kwargs.get('update_fields')
        if update_fields is None or ('conditions' in update_fields or 'sensor' in update_fields):
            self.state = self.get_evaluated_state()
        
        if self.state != old_state:
            from django.utils import timezone
            self.last_change = timezone.now()
            if update_fields is not None:
                kwargs['update_fields'] = list(update_fields) + ['last_change']
            
            # Send email if notification is enabled and not snoozed
            self.maybe_send_notification(old_state)

        super().save(*args, **kwargs)

    def maybe_send_notification(self, old_state):
        from django.utils import timezone
        if self.snooze_until and self.snooze_until > timezone.now():
            return

        should_send = False
        if self.state and not old_state and self.send_email_when_on:
            should_send = True
        elif not self.state and old_state and self.send_email_when_off:
            should_send = True
        
        if should_send:
            self.send_notification_email()

    def send_notification_email(self):
        from django.core.mail import EmailMultiAlternatives
        from django.template.loader import render_to_string
        from django.utils.html import strip_tags
        from django.conf import settings
        from django.urls import reverse
        from django.utils import timezone

        domain = getattr(settings, 'SITE_DOMAIN', 'localhost:8000')
        schema = "https" if not settings.DEBUG else "http"
        
        alarm_url = f"{schema}://{domain}" + reverse('admin:severynsor_alarm_change', args=[self.pk])
        
        # Determine actual sensor class for preview link
        sensor = self.sensor.get_real_instance()
        sensor_type = sensor._meta.model_name
        preview_url_name = f'severynsor_{sensor_type}_preview'
        sensor_url = f"{schema}://{domain}" + reverse(preview_url_name, args=[sensor.pk])

        context = {
            'alarm': self,
            'alarm_url': alarm_url,
            'sensor': sensor,
            'sensor_url': sensor_url,
            'timestamp': self.last_change or timezone.now()
        }

        subject = f"{'🔴' if self.state else '🟢'} {self.title} is {'ON' if self.state else 'OFF'}"
        html_content = render_to_string('emails/alarm_notification.html', context)
        text_content = strip_tags(html_content)

        msg = EmailMultiAlternatives(subject, text_content, settings.DEFAULT_FROM_EMAIL, [self.user.email])
        msg.attach_alternative(html_content, "text/html")
        msg.send()

    def recalculate(self):
        new_state = self.get_evaluated_state()
        if self.state != new_state:
            from django.utils import timezone
            self.state = new_state
            self.last_change = timezone.now()
            self.save(update_fields=['state', 'last_change'])

@receiver(post_save, sender='severynsor.ValueRecord')
def trigger_alarm_recalculation(sender, instance, created, **kwargs):
    if created:
        alarms = Alarm.objects.filter(sensor=instance.sensor)
        for alarm in alarms:
            alarm.recalculate()
