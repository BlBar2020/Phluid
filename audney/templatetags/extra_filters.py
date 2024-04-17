# Import the template module from Django
from django import template

# Create an instance of Library, which can store template tags and filters
register = template.Library()

# Define a custom template filter
@register.filter(name='is_equal_to')
def is_equal_to(value, arg):
    """
    This function checks if the value is equal to the argument.

    Args:
        value: The first value to compare.
        arg: The second value to compare.

    Returns:
        bool: True if value is equal to arg, False otherwise.
    """
    return value == arg
