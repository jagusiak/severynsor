import json
from django.conf import settings
from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.contrib.auth.models import User, Group
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.admin import GroupAdmin as BaseGroupAdmin
from django.forms import PasswordInput
from unfold.admin import ModelAdmin
from unfold.decorators import action
try:
    from unfold.datasets import BaseDataset
except ImportError:
    class BaseDataset:
        pass
from unfold.forms import AdminPasswordChangeForm, UserChangeForm, UserCreationForm
from polymorphic.admin import PolymorphicParentModelAdmin, PolymorphicChildModelAdmin, PolymorphicChildModelFilter
from .constants import MeasureType
from .models import Location, Sensor, ValueSensor, ImageSensor, Record, ValueRecord, ImageRecord, SensorRetriever, OpenMeteoRetriever, OpenWeatherMapRetriever, RTSPRetriever, SystemDataRetriever, TapoRetriever, ActivityLog, Alarm
from .widgets import ConditionBuilderWidget, PasswordToggleWidget


try:
    admin.site.unregister(User)
    admin.site.unregister(Group)
except admin.sites.NotRegistered:
    pass

@admin.register(User)
class UserAdmin(BaseUserAdmin, ModelAdmin):
    form = UserChangeForm
    add_form = UserCreationForm
    change_password_form = AdminPasswordChangeForm


@admin.register(Group)
class GroupAdmin(BaseGroupAdmin, ModelAdmin):
    pass

@admin.register(Location)
class LocationAdmin(ModelAdmin):
    list_display = ['name', 'latitude', 'longitude']
    search_fields = ['name']
    exclude = ['order']

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


class MeasureTypeFilter(admin.SimpleListFilter):
    title = 'Measure Type'
    parameter_name = 'measure_type'

    def lookups(self, request, model_admin):
        return MeasureType.choices

    def queryset(self, request, queryset):
        if self.value():
            return queryset.instance_of(ValueSensor).filter(valuesensor__measure_type=self.value())
        return queryset


class AlarmStatusFilter(admin.SimpleListFilter):
    title = 'Status'
    parameter_name = 'state'

    def lookups(self, request, model_admin):
        return (
            ('1', 'Alarm ON'),
            ('0', 'Alarm OFF'),
        )

    def queryset(self, request, queryset):
        if self.value() == '1':
            return queryset.filter(state=True)
        if self.value() == '0':
            return queryset.filter(state=False)
        return queryset


class SensorAdminMixin:
    @admin.display(description="Title", ordering="title")
    def display_title(self, obj):
        if obj.image:
            logo = format_html('<img src="{}" style="width: 28px; height: 28px; border-radius: 6px; object-fit: cover; box-shadow: 0 1px 2px rgba(0,0,0,0.1);" />', obj.image.url)
        else:
            logo = format_html('<div style="width: 28px; height: 28px; border-radius: 6px; background-color: #f3f4f6; display: flex; align-items: center; justify-content: center;"><span style="color: #9ca3af; font-size: 14px;">📸</span></div>')
            
        return format_html(
            '<div style="display: flex; align-items: center; gap: 10px;">{} <span class="font-semibold text-gray-900 dark:text-gray-100">{}</span></div>',
            logo, obj.title
        )

    @admin.display(description="Measure Type")
    def display_measure_type(self, obj):
        real_obj = obj.get_real_instance() if hasattr(obj, 'get_real_instance') else obj
        if isinstance(real_obj, ValueSensor):
            return real_obj.get_measure_type_display()
        return "-"

    @admin.display(description="Preview")
    def preview_link(self, obj):
        real_obj = obj.get_real_instance() if hasattr(obj, 'get_real_instance') else obj
        
        if isinstance(real_obj, ValueSensor):
            url = reverse('severynsor_valuesensor_preview', args=[real_obj.pk])
        elif isinstance(real_obj, ImageSensor):
            url = reverse('severynsor_imagesensor_preview', args=[real_obj.pk])
        else:
            return "-"
            
        return format_html(
            '<a href="{}" class="inline-flex items-center px-3 py-1 text-xs font-semibold rounded bg-primary-600 text-white hover:bg-primary-700 transition-colors shadow-sm" style="background-color: var(--color-primary-600, #0d9488); color: #ffffff; text-decoration: none;">'
            'Preview</a>',
            url
        )


class BaseSensorChildAdmin(SensorAdminMixin, ModelAdmin, PolymorphicChildModelAdmin):
    base_model = Sensor
    list_display = ['display_title', 'location', 'display_measure_type', 'placement', 'last_value', 'preview_link']
    actions_detail = ['preview_action']
    search_fields = ['title', 'location__name', 'placement']
    
    @admin.display(description="Last Value")
    def last_value(self, obj):
        record = obj.records.order_by('-timestamp').first()
        if record:
            if isinstance(obj, ValueSensor) and hasattr(record, 'value'):
                return f"{round(record.value, 2)} {getattr(obj, 'measure_unit', '')}"
            elif isinstance(obj, ImageSensor) and hasattr(record, 'image') and record.image:
                return "Has Image"
        return "-"

    @action(description="Preview", url_path="preview", icon="visibility")
    def preview_action(self, request, object_id):
        obj = self.get_object(request, object_id)
        if isinstance(obj, ValueSensor):
            url = reverse('severynsor_valuesensor_preview', args=[obj.pk])
        elif isinstance(obj, ImageSensor):
            url = reverse('severynsor_imagesensor_preview', args=[obj.pk])
        else:
            return None
        from django.http import HttpResponseRedirect
        return HttpResponseRedirect(url)


    def get_readonly_fields(self, request, obj=None):
        return ['api_example']

    @admin.display(description="API Usage Example")
    def api_example(self, obj):
        if not obj or not obj.pk:
            return "Save the sensor to see API example."
        
        token = str(obj.token)
        domain = getattr(settings, 'SITE_DOMAIN', 'localhost:8000')
        schema = "https" if not settings.DEBUG else "http"
        url = f"{schema}://{domain}/api/records/"
        
        if isinstance(obj, ValueSensor):
            payload = '{"value": 23.5}'
        elif isinstance(obj, ImageSensor):
            payload = '{"image": "<base64_data>"}'
        else:
            return "-"
            
        curl_cmd = f"curl -X POST {url} \\\n  -H \"Authorization: Bearer {token}\" \\\n  -H \"Content-Type: application/json\" \\\n  -d '{payload}'"
        
        return format_html(
            '''
            <div style="position: relative; background: #1e293b; color: #f8fafc; padding: 16px; border-radius: 8px; font-family: monospace; font-size: 13px; line-height: 1.5; overflow-x: auto; margin-top: 8px;">
                <pre id="curl-code-{pk}" style="margin: 0; white-space: pre-wrap;">{curl_cmd}</pre>
                <button type="button" onclick="copyToClipboard(this, 'curl-code-{pk}')" style="position: absolute; top: 8px; right: 8px; background: rgba(255,255,255,0.1); border: none; color: white; padding: 4px 8px; border-radius: 4px; cursor: pointer; display: flex; align-items: center; gap: 4px; font-size: 11px; transition: background 0.2s;">
                    <span class="material-symbols-outlined" style="font-size: 14px;">content_copy</span>
                    Copy
                </button>
            </div>
            <script>
            if (typeof copyToClipboard === 'undefined') {{
                window.copyToClipboard = function(btn, targetId) {{
                    const code = document.getElementById(targetId).innerText;
                    navigator.clipboard.writeText(code).then(() => {{
                        const originalHtml = btn.innerHTML;
                        btn.innerHTML = '<span class="material-symbols-outlined" style="font-size: 14px;">check</span> Copied!';
                        btn.style.background = 'rgba(34, 197, 94, 0.2)';
                        setTimeout(() => {{
                            btn.innerHTML = originalHtml;
                            btn.style.background = 'rgba(255,255,255,0.1)';
                        }}, 2000);
                    }});
                }}
            }}
            </script>
            ''',
            curl_cmd=curl_cmd,
            pk=obj.pk
        )

@admin.register(ValueSensor)
class ValueSensorAdmin(BaseSensorChildAdmin):
    base_model = Sensor
    change_form_datasets = [RecordDataset]

    def get_fieldsets(self, request, obj=None):
        data_fields = ['title', 'description', 'image', 'location', 'placement', 'measure_type']
        
        fieldsets = [
            (None, {
                'fields': data_fields
            }),
        ]

        if request.user.has_perm('severynsor.can_view_token'):
            fieldsets.append(('API Integration', {
                'fields': ['token', 'api_example'],
                'classes': ['collapse'] if obj else []
            }))

        return fieldsets
    

@admin.register(ImageSensor)
class ImageSensorAdmin(BaseSensorChildAdmin):
    base_model = Sensor
    change_form_datasets = [RecordDataset]

    def get_fieldsets(self, request, obj=None):
        data_fields = ['title', 'description', 'image', 'location', 'placement']
        
        fieldsets = [
            (None, {
                'fields': data_fields
            }),
        ]

        if request.user.has_perm('severynsor.can_view_token'):
            fieldsets.append(('API Integration', {
                'fields': ['token', 'api_example'],
                'classes': ['collapse'] if obj else []
            }))

        return fieldsets

    pass

@admin.register(Sensor)
class SensorAdmin(SensorAdminMixin, PolymorphicParentModelAdmin, ModelAdmin):
    base_model = Sensor
    child_models = (ValueSensor, ImageSensor)
    add_type_template = "admin/severynsor/sensor/choose_child_type.html"
    list_display = ['display_title', 'location', 'display_measure_type', 'placement', 'preview_link']
    list_filter = [PolymorphicChildModelFilter, MeasureTypeFilter, 'location', 'show_in_dashboard']

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

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        if db_field.name == 'api_key':
            kwargs['widget'] = PasswordToggleWidget()
        return super().formfield_for_dbfield(db_field, request, **kwargs)

@admin.register(RTSPRetriever)
class RTSPRetrieverAdmin(PolymorphicChildModelAdmin, ModelAdmin):
    base_model = SensorRetriever
    list_display = ['name', 'sensor', 'masked_rtsp_url', 'frequency_minutes', 'enabled']
    actions = [disable_retrievers, enable_retrievers]

    def get_readonly_fields(self, request, obj=None):
        ro = list(super().get_readonly_fields(request, obj))
        if obj and 'sensor' not in ro:
            ro.append('sensor')
        return ro

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        if db_field.name == 'rtsp_url':
            kwargs['widget'] = PasswordToggleWidget()
        return super().formfield_for_dbfield(db_field, request, **kwargs)

    @admin.display(description="RTSP URL")
    def masked_rtsp_url(self, obj):
        if not obj.rtsp_url:
            return "-"
        return "••••••••"

@admin.register(SystemDataRetriever)
class SystemDataRetrieverAdmin(PolymorphicChildModelAdmin, ModelAdmin):
    base_model = SensorRetriever
    list_display = ['name', 'sensor', 'frequency_minutes', 'enabled']
    list_filter = ['enabled']
    actions = [disable_retrievers, enable_retrievers]

    def get_readonly_fields(self, request, obj=None):
        ro = list(super().get_readonly_fields(request, obj))
        if obj and 'sensor' not in ro:
            ro.append('sensor')
        return ro

@admin.register(TapoRetriever)
class TapoRetrieverAdmin(PolymorphicChildModelAdmin, ModelAdmin):
    base_model = SensorRetriever
    list_display = ['name', 'sensor', 'frequency_minutes', 'enabled']
    list_filter = ['enabled']
    actions = [disable_retrievers, enable_retrievers]

    def get_readonly_fields(self, request, obj=None):
        ro = list(super().get_readonly_fields(request, obj))
        if obj and 'sensor' not in ro:
            ro.append('sensor')
        return ro

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        if db_field.name == 'password':
            kwargs['widget'] = PasswordToggleWidget()
        return super().formfield_for_dbfield(db_field, request, **kwargs)

@admin.register(SensorRetriever)
class SensorRetrieverAdmin(PolymorphicParentModelAdmin, ModelAdmin):
    base_model = SensorRetriever
    child_models = (OpenMeteoRetriever, OpenWeatherMapRetriever, RTSPRetriever, SystemDataRetriever, TapoRetriever)
    add_type_template = "admin/severynsor/sensorretriever/choose_child_type.html"
    list_filter = (PolymorphicChildModelFilter, 'enabled')
    list_display = ['name', 'sensor', 'frequency_minutes', 'enabled', 'get_retriever_name']
    actions = [disable_retrievers, enable_retrievers]

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

@admin.register(ActivityLog)
class ActivityLogAdmin(ModelAdmin):
    list_display = ['timestamp', 'display_type', 'display_target', 'status_badge', 'duration_display']
    list_filter = ['type', 'success', 'timestamp', 'sensor', 'retriever']
    search_fields = ['error_message', 'url', 'sensor__title', 'retriever__name']
    readonly_fields = ['type', 'sensor', 'retriever', 'timestamp', 'success', 'error_message', 'url', 'status_code', 'duration']
    
    @admin.display(description="Type")
    def display_type(self, obj):
        icon = "download" if obj.type == ActivityLog.RETRIEVER else "api"
        return format_html(
            '<div class="flex items-center gap-2 font-bold text-gray-900 dark:text-gray-100"><span class="material-symbols-outlined text-sm">{}</span> {}</div>',
            icon, obj.get_type_display()
        )

    @admin.display(description="Target")
    def display_target(self, obj):
        target_name = "-"
        if obj.retriever:
            target_name = obj.retriever.name or f"Retriever #{obj.retriever.pk}"
        elif obj.sensor:
            target_name = obj.sensor.title
            
        return format_html(
            '<span class="font-bold text-gray-900 dark:text-gray-100">{}</span>',
            target_name
        )

    @admin.display(description="Status")
    def status_badge(self, obj):
        if obj.success:
            return format_html(
                '<span class="inline-flex items-center px-2.5 py-1 rounded-md bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400 text-xs font-bold uppercase transition-colors">Success</span>'
            )
        return format_html(
            '<span class="inline-flex items-center px-2.5 py-1 rounded-md bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400 text-xs font-bold uppercase transition-colors">Error</span>'
        )

    @admin.display(description="Duration")
    def duration_display(self, obj):
        if obj.duration:
            return f"{obj.duration:.3f}s"
        return "-"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

@admin.register(Alarm)
class AlarmAdmin(ModelAdmin):
    list_display = ['title', 'sensor', 'sensor_value', 'status_badge', 'last_change', 'is_snoozed']
    list_filter = [AlarmStatusFilter, 'sensor', 'send_email_when_on', 'send_email_when_off']
    readonly_fields = ['status_display', 'last_change']
    exclude = ['user', 'state']
    
    fieldsets = [
        ('General', {
            'fields': ['title', 'sensor', 'status_display', 'last_change'],
            'classes': ['tab']
        }),
        ('Conditions', {
            'fields': ['conditions'],
            'classes': ['tab']
        }),
        ('Notifications', {
            'fields': ['send_email_when_on', 'send_email_when_off', 'snooze_until'],
            'classes': ['tab']
        }),
    ]

    def get_readonly_fields(self, request, obj=None):
        fields = super().get_readonly_fields(request, obj)
        if obj: # Editing an existing object
            if 'sensor' not in fields:
                fields = list(fields) + ['sensor']
        return fields

    @admin.display(description="Snoozed", boolean=True)
    def is_snoozed(self, obj):
        from django.utils import timezone
        return obj.snooze_until and obj.snooze_until > timezone.now()
    
    @admin.display(description="Status")
    def status_badge(self, obj):
        return self.state_badge(obj)
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(user=request.user)

    def save_model(self, request, obj, form, change):
        if not change:
            obj.user = request.user
        super().save_model(request, obj, form, change)

    def has_view_permission(self, request, obj=None):
        if obj is not None and not request.user.is_superuser and obj.user != request.user:
            return False
        return super().has_view_permission(request, obj)

    def has_change_permission(self, request, obj=None):
        if obj is not None and not request.user.is_superuser and obj.user != request.user:
            return False
        return super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        if obj is not None and not request.user.is_superuser and obj.user != request.user:
            return False
        return super().has_delete_permission(request, obj)

    def state_badge(self, obj):
        if obj.state:
             return format_html(
                '<span class="inline-flex items-center px-2.5 py-1 rounded-md bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400 text-xs font-bold uppercase">ALARM ON</span>'
            )
        return format_html(
            '<span class="inline-flex items-center px-2.5 py-1 rounded-md bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400 text-xs font-bold uppercase">Alarm OFF</span>'
        )

    @admin.display(description="Current Status")
    def status_display(self, obj):
        return self.state_badge(obj)

    @admin.display(description="Current Value")
    def sensor_value(self, obj):
        record = obj.sensor.records.order_by('-timestamp').first()
        if record:
            return record.display_value()
        return "-"
    state_badge.short_description = "State"

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        if db_field.name == 'conditions':
            kwargs['widget'] = ConditionBuilderWidget()
        return super().formfield_for_dbfield(db_field, request, **kwargs)

