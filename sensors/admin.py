import json
from django.conf import settings
from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from unfold.admin import ModelAdmin
from unfold.decorators import action
from unfold.datasets import BaseDataset
from polymorphic.admin import PolymorphicParentModelAdmin, PolymorphicChildModelAdmin, PolymorphicChildModelFilter
from .models import Location, Sensor, ValueSensor, ImageSensor, Record, ValueRecord, ImageRecord, SensorRetriever, OpenMeteoRetriever, OpenWeatherMapRetriever, RTSPRetriever

@admin.register(Location)
class LocationAdmin(ModelAdmin):
    list_display = ['name', 'latitude', 'longitude', 'order']
    list_editable = ['order']
    search_fields = ['name']
    
    class Media:
        css = {
            'all': ('https://unpkg.com/leaflet@1.9.4/dist/leaflet.css',)
        }
        js = (
            'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js',
            'js/location_map.js',
        )

@admin.action(description='Disable selected retrievers')
def disable_retrievers(modeladmin, request, queryset):
    queryset.update(enabled=False)

@admin.action(description='Enable selected retrievers')
def enable_retrievers(modeladmin, request, queryset):
    queryset.update(enabled=True)


class RecordDatasetAdmin(ModelAdmin):
    list_display = ['timestamp', 'display_value']
    list_per_page = 20
    ordering = ['-timestamp']

    def display_value(self, obj):
        return obj.display_value()
    display_value.short_description = "Value"

    def get_queryset(self, request):
        obj_id = self.extra_context.get("object")
        if not obj_id:
            return super().get_queryset(request).none()
        return super().get_queryset(request).filter(sensor__pk=obj_id)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class RecordDataset(BaseDataset):
    model = Record
    model_admin = RecordDatasetAdmin
    tab = True


class BaseSensorChildAdmin(ModelAdmin, PolymorphicChildModelAdmin):
    base_model = Sensor
    list_display = ['display_icon', 'title', 'location', 'last_value', 'preview_link']
    actions_detail = ['preview_action']
    search_fields = ['title', 'location']
    
    class Media:
        css = {
            'all': ('https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined',)
        }
    
    @admin.display(description="Icon")
    def display_icon(self, obj):
        if obj.image:
            return format_html('<img src="{}" style="width: 32px; height: 32px; border-radius: 6px; object-fit: cover; box-shadow: 0 1px 3px rgba(0,0,0,0.2);" />', obj.image.url)
        return format_html('<div style="width: 32px; height: 32px; border-radius: 6px; background-color: #e5e7eb; display: flex; align-items: center; justify-content: center;"><span style="color: #6b7280; font-size: 16px;">📸</span></div>')
        
    @admin.display(description="Last Value")
    def last_value(self, obj):
        record = obj.records.order_by('-timestamp').first()
        if record:
            if isinstance(obj, ValueSensor) and hasattr(record, 'value'):
                return f"{record.value} {getattr(obj, 'measure_unit', '')}"
            elif isinstance(obj, ImageSensor) and hasattr(record, 'image') and record.image:
                return "Has Image"
        return "-"
    
    @admin.display(description="Preview")
    def preview_link(self, obj):
        if isinstance(obj, ValueSensor):
            url = reverse('sensors_valuesensor_preview', args=[obj.pk])
        elif isinstance(obj, ImageSensor):
            url = reverse('sensors_imagesensor_preview', args=[obj.pk])
        else:
            return "-"
        return format_html(
            '<a href="{}" style="display: inline-flex; align-items: center; gap: 4px; '
            'padding: 4px 10px; border-radius: 6px; font-size: 12px; font-weight: 600; '
            'text-decoration: none; background: var(--color-primary-50, #f0fdfa); '
            'color: var(--color-primary-700, #0f766e); transition: all 0.15s;">'
            '<span class="material-symbols-outlined" style="font-size: 14px;">visibility</span>'
            'Preview</a>',
            url
        )

    @action(description="Preview", url_path="preview", icon="visibility")
    def preview_action(self, request, object_id):
        obj = self.get_object(request, object_id)
        if isinstance(obj, ValueSensor):
            url = reverse('sensors_valuesensor_preview', args=[obj.pk])
        elif isinstance(obj, ImageSensor):
            url = reverse('sensors_imagesensor_preview', args=[obj.pk])
        else:
            return None
        from django.http import HttpResponseRedirect
        return HttpResponseRedirect(url)

    @admin.display(description="")
    def sensor_header(self, obj):
        if not obj:
            return ""
        icon = self.display_icon(obj)
        title = obj.title or "-"
        desc = obj.description or "-"
        loc = obj.location.name if obj.location else "-"
        
        return format_html(
            '''
            <div>
                <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 4px;">
                    {}
                    <h2 style="margin: 0; font-size: 20px; font-weight: bold;">{}</h2>
                </div>
                <div style="color: #6b7280; font-style: italic; font-size: 14px; margin-left: 44px;">
                    {} <span style="margin: 0 8px;">|</span> {}
                </div>
            </div>
            ''',
            icon, title, desc, loc
        )

    def get_readonly_fields(self, request, obj=None):
        return ['sensor_header']

@admin.register(ValueSensor)
class ValueSensorAdmin(BaseSensorChildAdmin):
    base_model = Sensor
    change_form_datasets = [RecordDataset]

    def get_fieldsets(self, request, obj=None):
        data_fields = ['title', 'description', 'image', 'location', 'placement', 'measure_type', 'show_in_dashboard']
        if request.user.has_perm('sensors.can_view_token'):
            data_fields.append('token')

        fieldsets = [
            (None, {
                'fields': ['sensor_header']
            }),
            ('Edit Data', {
                'fields': data_fields
            }),
        ]

        if obj is None:
            fieldsets = [
                (None, {
                    'fields': data_fields
                }),
            ]

        return fieldsets

@admin.register(ImageSensor)
class ImageSensorAdmin(BaseSensorChildAdmin):
    base_model = Sensor
    change_form_datasets = [RecordDataset]

    def get_fieldsets(self, request, obj=None):
        data_fields = ['title', 'description', 'image', 'location', 'placement', 'show_in_dashboard']
        if request.user.has_perm('sensors.can_view_token'):
            data_fields.append('token')

        fieldsets = [
            (None, {
                'fields': ['sensor_header']
            }),
            ('Edit Data', {
                'fields': data_fields
            }),
        ]

        if obj is None:
            fieldsets = [
                (None, {
                    'fields': data_fields
                }),
            ]

        return fieldsets

    pass

@admin.register(Sensor)
class SensorAdmin(PolymorphicParentModelAdmin, ModelAdmin):
    base_model = Sensor
    child_models = (ValueSensor, ImageSensor)
    add_type_template = "admin/sensors/sensor/choose_child_type.html"
    list_display = ['title', 'location']

    class Media:
        css = {
            'all': ('https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined',)
        }

    def add_type_view(self, request, form_url=''):
        if self.child_models:
            choices = []
            for child in self.child_models:
                if not self.has_add_permission(request):
                    continue
                    
                model_name = child._meta.model_name
                url = reverse(f'admin:{child._meta.app_label}_{model_name}_add')
                if request.GET:
                    url += '?' + request.GET.urlencode()
                
                choices.append({
                    'name': child._meta.verbose_name,
                    'type': model_name,
                    'url': url,
                    'model': child,
                })
            
            if len(choices) == 1:
                from django.http import HttpResponseRedirect
                return HttpResponseRedirect(choices[0]['url'])
                
            context = {
                **self.admin_site.each_context(request),
                'title': f'Select {self.model._meta.verbose_name} type',
                'models': choices,
                'opts': self.model._meta,
                'app_label': self.model._meta.app_label,
                'media': self.media,
            }
            from django.shortcuts import render
            return render(request, self.add_type_template, context)
            
        return super().add_type_view(request, form_url)

# @admin.register(ValueRecord)
class ValueRecordAdmin(PolymorphicChildModelAdmin, ModelAdmin):
    base_model = Record
    list_display = ['sensor', 'value', 'timestamp']
    list_filter = ['sensor', 'timestamp']

    def has_change_permission(self, request, obj=None):
        return False

# @admin.register(ImageRecord)
class ImageRecordAdmin(PolymorphicChildModelAdmin, ModelAdmin):
    base_model = Record
    list_display = ['sensor', 'timestamp']
    list_filter = ['sensor', 'timestamp']

    def has_change_permission(self, request, obj=None):
        return False

# @admin.register(Record)
class RecordAdmin(PolymorphicParentModelAdmin, ModelAdmin):
    base_model = Record
    child_models = (ValueRecord, ImageRecord)
    list_filter = (PolymorphicChildModelFilter, 'sensor', 'timestamp')
    list_display = ['sensor', 'timestamp']

    def has_change_permission(self, request, obj=None):
        return False

@admin.register(OpenMeteoRetriever)
class OpenMeteoRetrieverAdmin(PolymorphicChildModelAdmin, ModelAdmin):
    base_model = SensorRetriever
    list_display = ['name', 'sensor', 'frequency_minutes', 'enabled']
    list_filter = ['enabled']
    actions = [disable_retrievers, enable_retrievers]

    def get_readonly_fields(self, request, obj=None):
        ro = list(super().get_readonly_fields(request, obj))
        if obj and 'sensor' not in ro:
            ro.append('sensor')
        return ro

@admin.register(OpenWeatherMapRetriever)
class OpenWeatherMapRetrieverAdmin(PolymorphicChildModelAdmin, ModelAdmin):
    base_model = SensorRetriever
    list_display = ['name', 'sensor', 'frequency_minutes', 'enabled']
    list_filter = ['enabled']
    actions = [disable_retrievers, enable_retrievers]

    def get_readonly_fields(self, request, obj=None):
        ro = list(super().get_readonly_fields(request, obj))
        if obj and 'sensor' not in ro:
            ro.append('sensor')
        return ro

@admin.register(RTSPRetriever)
class RTSPRetrieverAdmin(PolymorphicChildModelAdmin, ModelAdmin):
    base_model = SensorRetriever
    list_display = ['name', 'sensor', 'rtsp_url', 'frequency_minutes', 'enabled']
    actions = [disable_retrievers, enable_retrievers]

    def get_readonly_fields(self, request, obj=None):
        ro = list(super().get_readonly_fields(request, obj))
        if obj and 'sensor' not in ro:
            ro.append('sensor')
        return ro

@admin.register(SensorRetriever)
class SensorRetrieverAdmin(PolymorphicParentModelAdmin, ModelAdmin):
    base_model = SensorRetriever
    child_models = (OpenMeteoRetriever, OpenWeatherMapRetriever, RTSPRetriever)
    add_type_template = "admin/sensors/sensorretriever/choose_child_type.html"
    list_filter = (PolymorphicChildModelFilter, 'enabled')
    list_display = ['name', 'sensor', 'frequency_minutes', 'enabled', 'get_retriever_name']
    actions = [disable_retrievers, enable_retrievers]

    class Media:
        css = {
            'all': ('https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined',)
        }

    @admin.display(description='Retriever')
    def get_retriever_name(self, obj):
        return obj.get_real_instance_class().retriever_name

    def add_type_view(self, request, form_url=''):
        """
        Extending add_type_view to ensure models are correctly passed to our tiled template.
        """
        if self.child_models:
            choices = []
            for child in self.child_models:
                # Basic check for add permission
                if not self.has_add_permission(request):
                    continue
                    
                model_name = child._meta.model_name
                url = reverse(f'admin:{child._meta.app_label}_{model_name}_add')
                if request.GET:
                    url += '?' + request.GET.urlencode()
                
                choices.append({
                    'name': child._meta.verbose_name,
                    'type': model_name,
                    'url': url,
                    'model': child,
                })
            
            # If we only have one child model, redirect to its add view directly
            if len(choices) == 1:
                from django.http import HttpResponseRedirect
                return HttpResponseRedirect(choices[0]['url'])
                
            context = {
                **self.admin_site.each_context(request),
                'title': f'Select {self.model._meta.verbose_name} type',
                'models': choices,
                'opts': self.model._meta,
                'app_label': self.model._meta.app_label,
                'media': self.media,
            }
            from django.shortcuts import render
            return render(request, self.add_type_template, context)
            
        return super().add_type_view(request, form_url)
