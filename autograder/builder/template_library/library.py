"""Library module."""

import importlib.util
import inspect
import os
import tempfile

from autograder.builder.models.template import Template


class TemplateLibrary:
    @staticmethod
    def get_template(template_name: str, custom_template_content: str = None):
        if template_name == "custom":
            if not custom_template_content:
                raise ValueError(
                    "Custom template content must be provided for 'custom' template type."
                )
            return TemplateLibrary._load_custom_template_from_content(
                custom_template_content
            )

        if template_name == "web dev":
            from autograder.builder.template_library.templates.web_dev import (
                WebDevTemplate,
            )

            return WebDevTemplate()
        if template_name == "api":
            from autograder.builder.template_library.templates.api_testing import (
                ApiTestingTemplate,
            )

            return ApiTestingTemplate()
        if template_name == "essay":
            from autograder.builder.template_library.templates.essay_grader import (
                EssayGraderTemplate,
            )

            return EssayGraderTemplate()
        if template_name == "I/O":
            from autograder.builder.template_library.templates.input_output import (
                InputOutputTemplate,
            )

            return InputOutputTemplate()
        else:
            raise ValueError(f"Template '{template_name}' not found.")

    @staticmethod
    def _load_custom_template_from_content(template_content: str):
        """Load a custom template directly from string content without file placement."""
        spec = importlib.util.spec_from_loader("custom_template", loader=None)
        custom_module = importlib.util.module_from_spec(spec)

        # Execute the template code directly in the module namespace
        exec(template_content, custom_module.__dict__)

        # Find and return the Template subclass
        for name, obj in inspect.getmembers(custom_module):
            if (
                inspect.isclass(obj)
                and issubclass(obj, Template)
                and obj is not Template
            ):
                return obj()

        raise ImportError(
            "No class inheriting from 'Template' found in the custom template content."
        )

    @staticmethod
    def _load_custom_template(file_path: str):
        """Legacy method for file-based custom templates."""
        spec = importlib.util.spec_from_file_location("custom_template", file_path)
        custom_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(custom_module)

        for name, obj in inspect.getmembers(custom_module):
            if (
                inspect.isclass(obj)
                and issubclass(obj, Template)
                and obj is not Template
            ):
                return obj()

        raise ImportError(f"No class inheriting from 'Template' found in {file_path}")
