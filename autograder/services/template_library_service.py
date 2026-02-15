"""
Template Library Service

This service manages the loading and instantiation of grading templates.
It provides a centralized way to access templates and their metadata.

This is a singleton service that should be instantiated once at application startup.
"""

from typing import Dict, List, Optional
from autograder.models.abstract.template import Template
from autograder.template_library import TEMPLATE_REGISTRY, get_template_instance


class TemplateLibraryService:
    """
    Singleton service for managing and loading grading templates.

    This service provides methods to:
    - Load template instances by name
    - Retrieve template metadata
    - List available templates

    All templates are instantiated once and reused throughout the application lifecycle.
    """

    _instance: Optional['TemplateLibraryService'] = None
    _initialized: bool = False

    def __new__(cls):
        """Ensure only one instance of the service exists."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """Initialize the template library service and load all templates."""
        # Only initialize once
        if TemplateLibraryService._initialized:
            return

        self._templates: Dict[str, Template] = {}
        self._load_all_templates()
        TemplateLibraryService._initialized = True

    def _load_all_templates(self):
        """Load and cache all template instances at startup."""
        for template_name in TEMPLATE_REGISTRY.keys():
            try:
                self._templates[template_name] = get_template_instance(template_name)
            except Exception as e:
                # Log the error but continue loading other templates
                print(f"Warning: Failed to load template '{template_name}': {e}")

    @classmethod
    def get_instance(cls) -> 'TemplateLibraryService':
        """
        Get the singleton instance of the TemplateLibraryService.

        Returns:
            The singleton instance
        """
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls):
        """
        Reset the singleton instance. Useful for testing.
        This will stop all templates and clear the singleton.
        """
        if cls._instance is not None:
            for template in cls._instance._templates.values():
                try:
                    template.stop()
                except Exception:
                    pass
            cls._instance = None
            cls._initialized = False

    def start_template(self, template_name: str) -> Template:
        """
        Get the template instance based on the template name.

        Args:
            template_name: The identifier for the template (e.g., "webdev", "api", "essay", "IO")

        Returns:
            The singleton template instance

        Raises:
            KeyError: If the template name is not found in the registry
        """
        if template_name not in self._templates:
            available = ", ".join(self._templates.keys())
            raise KeyError(f"Template '{template_name}' not found. Available templates: {available}")

        return self._templates[template_name]

    def get_template_info(self, template_name: str) -> dict:
        """
        Return metadata about the template.

        Args:
            template_name: The identifier for the template

        Returns:
            A dictionary containing template metadata including:
            - name: The display name of the template
            - description: A description of what the template is for
            - requires_sandbox: Whether the template requires a sandbox environment
            - available_tests: List of available test function names

        Raises:
            KeyError: If the template name is not found in the registry
        """
        template = self.start_template(template_name)

        info = {
            "identifier": template_name,
            "name": template.template_name,
            "description": template.template_description,
            "requires_sandbox": template.requires_sandbox,
            "available_tests": list(template.tests.keys()) if hasattr(template, 'tests') else []
        }

        return info

    def list_available_templates(self) -> List[str]:
        """
        Get a list of all available template identifiers.

        Returns:
            A list of template identifier strings
        """
        return list(TEMPLATE_REGISTRY.keys())

    def get_all_templates_info(self) -> List[dict]:
        """
        Get metadata for all available templates.

        Returns:
            A list of dictionaries containing metadata for each template
        """
        return [self.get_template_info(name) for name in self.list_available_templates()]


    def get_test_function(self, template_name: str, test_name: str):
        """
        Get a specific test function from a template.

        Args:
            template_name: The identifier for the template
            test_name: The name of the test function to retrieve

        Returns:
            The test function instance

        Raises:
            KeyError: If the template is not found
            AttributeError: If the test is not found in the template
        """
        template = self.start_template(template_name)
        return template.get_test(test_name)

    def load_builtin_template(self, template_name: str) -> Template:
        """
        Load a built-in template from the template library.
        This is an alias for start_template for backward compatibility.

        Args:
            template_name: The identifier for the template

        Returns:
            The template instance

        Raises:
            KeyError: If the template name is not found in the registry
        """
        return self.start_template(template_name)

    def load_custom_template(self, custom_template):
        """
        Load a custom template provided by the user.

        TODO: Implement custom template loading with sandboxed environment.

        Args:
            custom_template: The custom template data/code

        Returns:
            The loaded custom template instance

        Raises:
            NotImplementedError: This feature is not yet implemented
        """
        raise NotImplementedError("Custom template loading is not yet implemented. This feature requires sandboxed environment support.")

