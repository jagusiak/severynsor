import json
from datetime import timedelta

from django.contrib import admin
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import permission_required
from django.db.models import Avg, Min, Max
from django.db.models.functions import TruncMinute, TruncHour, TruncDay, TruncWeek
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View
from rest_framework import generics
from rest_framework.permissions import BasePermission

from .authentication import BearerSensorAuthentication
from .models import (
    Location, Sensor, Record, ValueSensor, ImageSensor, ValueRecord, ImageRecord,
    SensorRetriever, RTSPRetriever,
)
from .serializers import RecordSerializer


class IsSensorAuthenticated(BasePermission):
    def has_permission(self, request, view):
        return bool(request.auth)


class RecordCreateView(generics.CreateAPIView):
    serializer_class = RecordSerializer
    authentication_classes = [BearerSensorAuthentication]
    permission_classes = [IsSensorAuthenticated]

    def perform_create(self, serializer):
        from .models.log import ActivityLog
        import time
        
        start_time = timezone.now()
        start_ts = time.time()
        
        try:
            instance = serializer.save()
            duration = time.time() - start_ts
            
            ActivityLog.objects.create(
                type=ActivityLog.API_CALL,
                sensor=instance.sensor if hasattr(instance, 'sensor') else None,
                timestamp=start_time,
                success=True,
                duration=duration,
                url=self.request.build_absolute_uri()
            )
        except Exception as e:
            duration = time.time() - start_ts
            # Attempt to get sensor from request auth if available
            sensor = self.request.auth if hasattr(self.request, 'auth') else None
            
            ActivityLog.objects.create(
                type=ActivityLog.API_CALL,
                sensor=sensor,
                timestamp=start_time,
                success=False,
                error_message=str(e),
                duration=duration,
                url=self.request.build_absolute_uri()
            )
            raise e


# ─── Preview Views ────────────────────────────────────────────────────────


def _check_preview_permission(user):
    return user.is_staff and user.has_perm('severynsor.can_preview_sensor')


@staff_member_required
def value_sensor_preview(request, object_id):
    if not request.user.has_perm('severynsor.can_preview_sensor'):
        from django.http import HttpResponseForbidden
        return HttpResponseForbidden("You don't have permission to preview sensor data.")

    sensor = get_object_or_404(ValueSensor, pk=object_id)
    context = {
        **admin.site.each_context(request),
        'sensor': sensor,
        'title': f'Preview – {sensor.title}',
        'has_permission': True,
        'is_popup': False,
        'is_nav_sidebar_enabled': True,
        'opts': ValueSensor._meta,
    }
    return render(request, 'admin/severynsor/valuesensor/preview.html', context)


@staff_member_required
def image_sensor_preview(request, object_id):
    if not request.user.has_perm('severynsor.can_preview_sensor'):
        from django.http import HttpResponseForbidden
        return HttpResponseForbidden("You don't have permission to preview sensor data.")

    sensor = get_object_or_404(ImageSensor, pk=object_id)

    # Check for RTSP retrievers
    rtsp_retriever = RTSPRetriever.objects.filter(sensor=sensor, enabled=True).first()
    has_live = rtsp_retriever is not None
    retriever_id = rtsp_retriever.id if has_live else None

    context = {
        **admin.site.each_context(request),
        'sensor': sensor,
        'has_live': has_live,
        'retriever_id': retriever_id,
        'title': f'Preview – {sensor.title}',
        'has_permission': True,
        'is_popup': False,
        'is_nav_sidebar_enabled': True,
        'opts': ImageSensor._meta,
    }
    return render(request, 'admin/severynsor/imagesensor/preview.html', context)


# ─── API endpoints for preview dynamic data ───────────────────────────────


@staff_member_required
def value_sensor_chart_data(request, object_id):
    """Return aggregated chart data for a ValueSensor."""
    if not request.user.has_perm('severynsor.can_preview_sensor'):
        return JsonResponse({'error': 'Permission denied'}, status=403)

    sensor = get_object_or_404(ValueSensor, pk=object_id)

    # Parse params
    time_range = request.GET.get('time_range', 'last_day')
    bucket = request.GET.get('bucket', '1hour')
    agg_func = request.GET.get('agg_func', 'avg')

    now = timezone.now()
    ranges = {
        'last_hour': timedelta(hours=1),
        'last_6h': timedelta(hours=6),
        'last_day': timedelta(days=1),
        'last_week': timedelta(weeks=1),
        'last_month': timedelta(days=30),
        'last_year': timedelta(days=365),
    }
    start_time = now - ranges.get(time_range, timedelta(days=1))

    records = ValueRecord.objects.filter(sensor=sensor, timestamp__gte=start_time)

    # Bucket (truncation)
    trunc_map = {
        '1min': TruncMinute('timestamp'),
        '5min': TruncMinute('timestamp'),  # we'll handle 5min manually
        '1hour': TruncHour('timestamp'),
        '1day': TruncDay('timestamp'),
        '1week': TruncWeek('timestamp'),
    }

    agg_map = {
        'min': Min('value'),
        'avg': Avg('value'),
        'max': Max('value'),
    }
    agg_expression = agg_map.get(agg_func, Avg('value'))

    if bucket == '5min':
        # 5-minute buckets: use raw annotation with integer division
        from django.db.models import F, ExpressionWrapper, IntegerField
        from django.db.models.functions import Extract

        # We'll use TruncMinute then round down in Python
        chart_data = list(
            records
            .annotate(time_bucket=TruncMinute('timestamp'))
            .values('time_bucket')
            .annotate(agg_value=agg_expression)
            .order_by('time_bucket')
        )

        # Group into 5-min buckets
        from collections import OrderedDict
        buckets_5min = OrderedDict()
        for row in chart_data:
            dt = row['time_bucket']
            rounded_minute = (dt.minute // 5) * 5
            bucket_key = dt.replace(minute=rounded_minute, second=0, microsecond=0)
            if bucket_key not in buckets_5min:
                buckets_5min[bucket_key] = []
            buckets_5min[bucket_key].append(row['agg_value'])

        # Re-aggregate
        labels = []
        data = []
        for bk, vals in buckets_5min.items():
            labels.append(bk.strftime('%Y-%m-%d %H:%M'))
            vals_clean = [v for v in vals if v is not None]
            if vals_clean:
                if agg_func == 'min':
                    data.append(round(float(min(vals_clean)), 2))
                elif agg_func == 'max':
                    data.append(round(float(max(vals_clean)), 2))
                else:
                    data.append(round(float(sum(vals_clean) / len(vals_clean)), 2))
            else:
                data.append(None)
    else:
        trunc = trunc_map.get(bucket, TruncHour('timestamp'))
        chart_data = list(
            records
            .annotate(time_bucket=trunc)
            .values('time_bucket')
            .annotate(agg_value=agg_expression)
            .order_by('time_bucket')
        )
        labels = [row['time_bucket'].strftime('%Y-%m-%d %H:%M') for row in chart_data]
        data = [round(float(row['agg_value']), 2) if row['agg_value'] is not None else None for row in chart_data]

    # Also compute summary stats
    agg_all = records.aggregate(avg=Avg('value'), min=Min('value'), max=Max('value'))

    return JsonResponse({
        'labels': labels,
        'data': data,
        'sensor_title': sensor.title,
        'measure_unit': sensor.measure_unit,
        'measure_type': sensor.get_measure_type_display(),
        'stats': {
            'avg': round(agg_all['avg'], 2) if agg_all['avg'] is not None else None,
            'min': round(agg_all['min'], 2) if agg_all['min'] is not None else None,
            'max': round(agg_all['max'], 2) if agg_all['max'] is not None else None,
        },
        'record_count': records.count(),
    })


@staff_member_required
def image_sensor_history_data(request, object_id):
    """Return image record dates/search for ImageSensor preview."""
    if not request.user.has_perm('severynsor.can_preview_sensor'):
        return JsonResponse({'error': 'Permission denied'}, status=403)

    sensor = get_object_or_404(ImageSensor, pk=object_id)

    action = request.GET.get('action', 'dates')

    if action == 'dates':
        # Return all dates that have images (for calendar annotation)
        from django.db.models import Count
        from django.db.models.functions import TruncDate
        
        date_counts = (
            ImageRecord.objects.filter(sensor=sensor, image__isnull=False)
            .exclude(image='')
            .annotate(date=TruncDate('timestamp'))
            .values('date')
            .annotate(count=Count('id'))
            .order_by('date')
        )
        
        return JsonResponse({
            'dates': {d['date'].strftime('%Y-%m-%d'): d['count'] for d in date_counts},
        })

    elif action == 'search':
        # Search by date and optional time
        date_str = request.GET.get('date', '')
        time_str = request.GET.get('time', '')

        from datetime import datetime as dt
        
        if not date_str:
            return JsonResponse({'images': []})

        try:
            target_date = dt.strptime(date_str, '%Y-%m-%d').date()
            
            qs = ImageRecord.objects.filter(
                sensor=sensor,
                image__isnull=False,
                timestamp__date=target_date,
            ).exclude(image='').order_by('timestamp')

            # Optional time filtering (closest to)
            if time_str:
                try:
                    # simplistic time filter for now, could be improved to find 'closest'
                    # for now we just filter by the day and maybe limit or order
                    pass
                except ValueError:
                    pass

            images = []
            for rec in qs[:100]:  # Increased limit slightly
                try:
                    # Ensure the image actually exists in the DB record
                    if rec.image:
                        images.append({
                            'id': rec.id,
                            'url': rec.image.url,
                            'timestamp': rec.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                            'time': rec.timestamp.strftime('%H:%M:%S'),
                        })
                except Exception:
                    continue

            return JsonResponse({'images': images})
        except ValueError:
            return JsonResponse({'images': [], 'error': 'Invalid date format'}, status=400)
        except Exception as e:
            return JsonResponse({'images': [], 'error': str(e)}, status=500)

    return JsonResponse({'error': 'Invalid action'}, status=400)

@staff_member_required
def dashboard_settings(request):
    if not request.user.has_perm('severynsor.manage_dashboard'):
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied
        
    locations = Location.objects.prefetch_related('sensor_set').all().order_by('order', 'name')
        
    context = {
        **admin.site.each_context(request),
        'title': 'Dashboard Settings',
        'locations': locations,
        'opts': Location._meta,
    }
    return render(request, 'admin/severynsor/dashboard_settings.html', context)


@staff_member_required
def dashboard_settings_save(request):
    if not request.user.has_perm('severynsor.manage_dashboard'):
        from django.http import JsonResponse
        return JsonResponse({'status': 'error', 'message': 'Permission denied'}, status=403)
        
    if request.method == 'POST':
        order_raw = request.POST.get('order', '')
        if order_raw:
            order_ids = order_raw.split(',')
            from django.db import transaction
            try:
                with transaction.atomic():
                    for index, pk in enumerate(order_ids):
                        Location.objects.filter(pk=pk).update(order=index)
                
                from django.contrib import messages
                messages.success(request, 'Dashboard settings updated')
            except Exception as e:
                from django.contrib import messages
                messages.error(request, f'Error saving order: {e}')
        
        from django.shortcuts import redirect
        return redirect('admin:index')
        
    from django.http import HttpResponseNotAllowed
    return HttpResponseNotAllowed(['POST'])


@staff_member_required
def sensor_toggle_dashboard(request):
    if not request.user.has_perm('severynsor.manage_dashboard'):
        return JsonResponse({'status': 'error', 'message': 'Permission denied'}, status=403)
        
    try:
        data = json.loads(request.body)
        sensor_id = data.get('sensor_id')
        show = data.get('show')
        
        sensor = Sensor.objects.get(pk=sensor_id)
        sensor.show_in_dashboard = show
        sensor.save()
        return JsonResponse({'status': 'success'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)


@staff_member_required
def summary_stats(request):
    if not request.user.has_perm('severynsor.view_summary'):
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied
        
    from django.contrib.auth.models import User
    from .models.log import ActivityLog
    from .models.alarm import Alarm
    from .utils import get_media_size
    
    # Calculate stats
    total_sensors = Sensor.objects.count()
    active_sensors = Sensor.objects.filter(retrievers__enabled=True).distinct().count()
    
    total_records = Record.objects.count()
    value_records = ValueRecord.objects.count()
    image_records = ImageRecord.objects.count()
    
    total_retrievers = SensorRetriever.objects.count()
    active_retrievers = SensorRetriever.objects.filter(enabled=True).count()
    
    media_size_bytes = get_media_size()
    # Format media size
    if media_size_bytes < 1024:
        media_size = f"{media_size_bytes} B"
    elif media_size_bytes < 1024**2:
        media_size = f"{round(media_size_bytes / 1024, 2)} KB"
    elif media_size_bytes < 1024**3:
        media_size = f"{round(media_size_bytes / 1024**2, 2)} MB"
    else:
        media_size = f"{round(media_size_bytes / 1024**3, 2)} GB"
        
    total_logs = ActivityLog.objects.count()
    total_failures = ActivityLog.objects.filter(success=False).count()
    
    total_alarms = Alarm.objects.count()
    total_users = User.objects.count()
    
    context = {
        **admin.site.each_context(request),
        'title': 'System Summary',
        'stats': {
            'sensors': {
                'total': total_sensors,
                'active': active_sensors,
            },
            'retrievers': {
                'total': total_retrievers,
                'active': active_retrievers,
            },
            'records': {
                'total': total_records,
                'value': value_records,
                'image': image_records,
            },
            'media': {
                'size': media_size,
            },
            'logs': {
                'total': total_logs,
                'failures': total_failures,
            },
            'alarms': {
                'total': total_alarms,
            },
            'users': {
                'total': total_users,
            }
        }
    }
    return render(request, 'admin/severynsor/summary.html', context)
