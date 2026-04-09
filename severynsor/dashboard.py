from datetime import timedelta
import json
from django.utils import timezone
from django.db.models import Avg, Min, Max
from django.db.models.functions import TruncMinute, TruncHour, TruncDay

def dashboard_callback(request, context):
    from severynsor.models import Location, ValueSensor, ImageSensor, ValueRecord, ImageRecord

    time_range = request.GET.get('time_range', 'last_day')
    granularity = request.GET.get('granularity', 'hours')
    
    if time_range in ['last_week', 'last_month', 'last_year']:
        if granularity == 'minutes':
            granularity = 'hours'
            
    if time_range in ['last_month', 'last_year']:
        if granularity == 'hours':
            granularity = 'days'

    now = timezone.now()
    if time_range == 'last_hour':
        start_time = now - timedelta(hours=1)
    elif time_range == 'last_day':
        start_time = now - timedelta(days=1)
    elif time_range == 'last_week':
        start_time = now - timedelta(weeks=1)
    elif time_range == 'last_month':
        start_time = now - timedelta(days=30)
    elif time_range == 'last_year':
        start_time = now - timedelta(days=365)
    else:
        start_time = now - timedelta(days=1)

    locations = Location.objects.order_by('order', 'name')
    
    dashboard_data = []
    
    colors = [
        "var(--color-primary-600)",
        "var(--color-success-600)",
        "var(--color-warning-600)",
        "var(--color-danger-600)",
        "var(--color-info-600)"
    ]

    for loc in locations:
        severynsor = loc.sensor_set.filter(show_in_dashboard=True)
        if not severynsor.exists():
            continue
            
        value_severynsor = severynsor.instance_of(ValueSensor)
        image_severynsor = severynsor.instance_of(ImageSensor)
        
        loc_data = {
            'location': loc,
            'map_link': f"https://www.google.com/maps?q={loc.latitude},{loc.longitude}",
            'value_severynsor_table': [],
            'charts': {},
            'images': []
        }
        
        for vs in value_severynsor:
            records = ValueRecord.objects.filter(sensor=vs, timestamp__gte=start_time)
            
            agg = records.aggregate(avg=Avg('value'), min=Min('value'), max=Max('value'))
            if records.exists():
                loc_data['value_severynsor_table'].append({
                    'sensor': vs,
                    'avg': round(agg['avg'], 2) if agg['avg'] is not None else '-',
                    'min': round(agg['min'], 2) if agg['min'] is not None else '-',
                    'max': round(agg['max'], 2) if agg['max'] is not None else '-',
                    'measure_unit': vs.measure_unit
                })
            
            if granularity == 'minutes':
                trunc = TruncMinute('timestamp')
            elif granularity == 'hours':
                trunc = TruncHour('timestamp')
            else:
                trunc = TruncDay('timestamp')
                
            chart_data = list(records.annotate(time_bucket=trunc).values('time_bucket').annotate(avg_value=Avg('value')).order_by('time_bucket'))
            
            if chart_data:
                m_type = vs.measure_type
                if m_type not in loc_data['charts']:
                    loc_data['charts'][m_type] = []
                
                loc_data['charts'][m_type].append({
                    'sensor': vs,
                    'data': [round(float(d['avg_value']), 2) for d in chart_data],
                    'labels': [d['time_bucket'].strftime('%Y-%m-%d %H:%M') for d in chart_data]
                })
                
        # prepare table component data
        loc_data['table'] = {
            'headers': ['Sensor', 'Average', 'Min', 'Max', ''],
            'rows': []
        }
        for r in loc_data['value_severynsor_table']:
            from django.urls import reverse
            from django.utils.safestring import mark_safe
            try:
                url = reverse('admin:severynsor_valuesensor_change', args=[r['sensor'].pk])
            except:
                url = "#"
            try:
                preview_url = reverse('severynsor_valuesensor_preview', args=[r['sensor'].pk])
            except:
                preview_url = "#"
                
            image_tag = f'<img src="{r["sensor"].image.url}" class="w-5 h-5 rounded-full inline-block mr-2 object-cover border border-gray-200 dark:border-gray-700" />' if bool(r["sensor"].image) else ''
            
            loc_data['table']['rows'].append([
                mark_safe(f'<a href="{url}" class="font-medium text-primary-600 dark:text-primary-500 hover:underline md:inline-flex items-center">{image_tag}{r["sensor"].title}</a>'),
                f"{r['avg']} {r['measure_unit']}",
                f"{r['min']} {r['measure_unit']}",
                f"{r['max']} {r['measure_unit']}",
                mark_safe(f'<a href="{preview_url}" class="inline-flex items-center px-3 py-1 text-xs font-semibold rounded bg-primary-600 text-white hover:bg-primary-700 transition-colors shadow-sm">Preview</a>')
            ])
                
        # merge charts
        charts_formatted = []
        for m_type, datasets in loc_data['charts'].items():
            all_labels = set()
            for ds in datasets:
                for l in ds['labels']:
                    all_labels.add(l)
            sorted_labels = sorted(list(all_labels))
            
            aligned_datasets = []
            for idx, ds in enumerate(datasets):
                label_to_val = dict(zip(ds['labels'], ds['data']))
                aligned_data = [label_to_val.get(lbl, None) for lbl in sorted_labels]
                
                measure_unit = " " + getattr(ds['sensor'], 'measure_unit', '')
                color = colors[idx % len(colors)]
                
                aligned_datasets.append({
                    'label': ds['sensor'].title,
                    'data': aligned_data,
                    'type': 'line',
                    'borderColor': color,
                    'backgroundColor': color,
                    'displayYAxis': True,
                    'suffixYAxis': measure_unit,
                    'spanGaps': True
                })
                
            chart_json = json.dumps({
                'labels': sorted_labels,
                'datasets': aligned_datasets
            })
            
            legend_items = [{
                'label': ds['sensor'].title, 
                'color': colors[idx % len(colors)],
                'image_url': ds['sensor'].image.url if bool(ds['sensor'].image) else None
            } for idx, ds in enumerate(datasets)]
            
            sensor_images = list(set([ds['sensor'].image.url for ds in datasets if bool(ds['sensor'].image)]))
            images_html = "".join([f'<img src="{url}" class="w-5 h-5 rounded-full inline-block mr-1 object-cover border border-gray-200 dark:border-gray-700" />' for url in sensor_images])
            display_name = datasets[0]['sensor'].get_measure_type_display()
            title_html = mark_safe(f'<div class="flex items-center">{images_html}<span>{display_name}</span></div>')
            
            charts_formatted.append({
                'measure_type': m_type,
                'title_html': title_html,
                'data': chart_json,
                'legend_items': legend_items
            })
            
        loc_data['charts_formatted'] = charts_formatted
                
        for isen in image_severynsor:
            latest = ImageRecord.objects.filter(sensor=isen).order_by('-timestamp').first()
            if latest and bool(latest.image):
                from django.urls import reverse
                try:
                    url = reverse('admin:severynsor_imagesensor_change', args=[isen.pk])
                except:
                    url = "#"
                try:
                    preview_url = reverse('severynsor_imagesensor_preview', args=[isen.pk])
                except:
                    preview_url = url
                loc_data['images'].append({
                    'sensor': isen,
                    'sensor_image_url': isen.image.url if bool(isen.image) else None,
                    'title': f"{isen.title}",
                    'image_url': latest.image.url,
                    'edit_url': url,
                    'preview_url': preview_url,
                    'timestamp': latest.timestamp
                })
                
        if loc_data['value_severynsor_table'] or loc_data['charts_formatted'] or loc_data['images']:
            dashboard_data.append(loc_data)

    context.update({
        'title': 'Dashboard',
        'dashboard_data': dashboard_data,
        'time_range': time_range,
        'granularity': granularity,
    })
    
    return context
