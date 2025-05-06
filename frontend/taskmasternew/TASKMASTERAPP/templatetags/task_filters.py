from django import template

register = template.Library()

@register.filter
def split_tags(value):
    """
    Split a comma-separated string of tags into a list
    """
    if isinstance(value, list):
        return value  # Return the list as-is if it's already a list
    if not value:
        return []
    return [tag.strip() for tag in value.split(',')]