"""
Custom template filters for the dashboard app
"""
import json
from django import template
from django.utils.safestring import mark_safe

register = template.Library()


@register.filter(name='tojson')
def tojson(value):
    """
    Convert a Python object to JSON string
    Usage: {{ my_dict|tojson }}
    """
    try:
        return mark_safe(json.dumps(value))
    except (TypeError, ValueError):
        return mark_safe('{}')
