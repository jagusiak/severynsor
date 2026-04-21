import json
from django import forms
from django.template.loader import render_to_string
from django.utils.safestring import mark_safe

class ConditionBuilderWidget(forms.Widget):
    template_name = 'admin/severynsor/alarm/condition_builder.html'

    def render(self, name, value, attrs=None, renderer=None):
        if value is None:
            value = {}
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except json.JSONDecodeError:
                value = {}
        
        context = {
            'name': name,
            'value': json.dumps(value),
            'attrs': attrs,
        }
        return mark_safe(render_to_string(self.template_name, context))

class PasswordToggleWidget(forms.PasswordInput):
    template_name = 'admin/severynsor/widgets/password_toggle.html'

    def __init__(self, *args, **kwargs):
        kwargs.setdefault('render_value', True)
        super().__init__(*args, **kwargs)

    class Media:
        js = ('js/password_toggle.js',)
