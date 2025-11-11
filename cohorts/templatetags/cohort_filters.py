from django import template

register = template.Library()


@register.filter
def cents_to_dollars(cents):
    """Convert cents to dollars for display."""
    if cents is None:
        return "0"
    return str(int(cents / 100))

