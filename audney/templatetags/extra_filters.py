# Import the template module from Django
from django import template
from django.utils.safestring import mark_safe

# Create an instance of Library, which can store template tags and filters
register = template.Library()

# Define a custom template filter to check if value is equal to an argument
@register.filter(name='is_equal_to')
def is_equal_to(value, arg):
    return value == arg

# Define a custom template filter to add a CSS class to form fields
@register.filter(name='add_class')
def add_class(value, css_class):
    """
    Adds a CSS class to a form field widget if the value is a form field.

    Args:
        value: The form field.
        css_class: The CSS class to add.

    Returns:
        The form field with the added CSS class, or the value if not a form field.
    """
    try:
        return value.as_widget(attrs={'class': css_class})
    except AttributeError:
        # If it's not a form field, return it unchanged
        return value
