from django import template
from projects.models import ProjectMembership

register = template.Library()

@register.filter(name='endswith')
def endswith(value, arg):
    """
    Custom template filter to check if a string ends with a specific substring.
    Usage: {{ some_string|endswith:".csv" }}
    """
    return str(value).lower().endswith(str(arg).lower())

@register.filter(name='filter_by_status')
def filter_by_status(queryset, status):
    return queryset.filter(status=status)

@register.filter(name='truncate_badge')
def truncate_badge(value):
    try:
        val = int(value)
        if val > 9:
            return '9+'
        return val
    except (ValueError, TypeError):
        return value
    
@register.filter(name='has_project_role')
def has_project_role(user, project):
    """
    Checks the role of a given user on a specific project.
    Returns the role name (e.g., 'admin', 'editor') or None.
    """
    # Owner is a special case, not a membership object
    if project.owner == user:
        return 'owner'
    
    try:
        membership = ProjectMembership.objects.get(project=project, user=user)
        return membership.role
    except ProjectMembership.DoesNotExist:
        return None