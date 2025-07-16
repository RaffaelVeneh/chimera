from django import template

register = template.Library()

@register.filter(name='split')
def split(value, key=','):
    """
    Returns the value turned into a list, splitting by the key.
    Default key is a comma.
    """
    if value:
        return value.split(key)
    return []

@register.filter(name='strip')
def strip(value):
    """
    Calls the .strip() method on a value.
    """
    return str(value).strip()