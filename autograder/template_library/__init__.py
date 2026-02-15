"""
Template Library Module

This module provides a registry for all available templates in the autograder system.
Templates can be accessed by their string identifiers through the TEMPLATE_REGISTRY.
"""

from autograder.template_library.web_dev import WebDevTemplate
from autograder.template_library.api_testing import ApiTestingTemplate
from autograder.template_library.input_output import InputOutputTemplate

# Template Registry: Maps template identifiers to their template classes
TEMPLATE_REGISTRY = {
    "webdev": WebDevTemplate,
    "api": ApiTestingTemplate,
    "IO": InputOutputTemplate,
}


def get_template(template_name: str):
    """
    Retrieve a template class by its string identifier.

    Args:
        template_name: The string identifier for the template (e.g., "webdev", "api", "essay", "IO")

    Returns:
        The template class corresponding to the given identifier

    Raises:
        KeyError: If the template name is not found in the registry
    """
    if template_name not in TEMPLATE_REGISTRY:
        available = ", ".join(TEMPLATE_REGISTRY.keys())
        raise KeyError(f"Template '{template_name}' not found. Available templates: {available}")

    return TEMPLATE_REGISTRY[template_name]


def get_template_instance(template_name: str):
    """
    Retrieve an instantiated template by its string identifier.

    Args:
        template_name: The string identifier for the template (e.g., "webdev", "api", "essay", "IO")

    Returns:
        An instance of the template class corresponding to the given identifier

    Raises:
        KeyError: If the template name is not found in the registry
    """
    template_class = get_template(template_name)
    return template_class()


__all__ = [
    "TEMPLATE_REGISTRY",
    "get_template",
    "get_template_instance",
    "WebDevTemplate",
    "ApiTestingTemplate",
    "InputOutputTemplate",
]

