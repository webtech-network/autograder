import importlib.util
import inspect
import tempfile
import os
from autograder.builder.models.template import Template


class TemplateLibrary:
    @staticmethod
    def get_template(template_name: str, custom_template_content: str = None, clean=False):
        if template_name == "custom":
            if not custom_template_content:
                raise ValueError("Custom template content must be provided for 'custom' template type.")
            return TemplateLibrary._load_custom_template_from_content(custom_template_content)

        if template_name == "web dev":
            from autograder.builder.template_library.templates.web_dev import WebDevTemplate
            return WebDevTemplate(clean)
        if template_name == "api":
            from autograder.builder.template_library.templates.api_testing import ApiTestingTemplate
            return ApiTestingTemplate(clean)
        if template_name == "essay":
            from autograder.builder.template_library.templates.essay_grader import EssayGraderTemplate
            return EssayGraderTemplate(clean)
        if template_name == "io":
            from autograder.builder.template_library.templates.input_output import InputOutputTemplate
            return InputOutputTemplate(clean)
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
            if inspect.isclass(obj) and issubclass(obj, Template) and obj is not Template:
                return obj()

        raise ImportError("No class inheriting from 'Template' found in the custom template content.")

    @staticmethod
    def _load_custom_template(file_path: str):
        """Legacy method for file-based custom templates."""
        spec = importlib.util.spec_from_file_location("custom_template", file_path)
        custom_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(custom_module)

        for name, obj in inspect.getmembers(custom_module):
            if inspect.isclass(obj) and issubclass(obj, Template) and obj is not Template:
                return obj()

        raise ImportError(f"No class inheriting from 'Template' found in {file_path}")
    

    @staticmethod
    def get_template_info(template_name: str)-> dict:
        """Gets all the details of a template.
        param template_name: The name of the template to retrieve.
        return: A dictionary with all the template details.
        example:
        {
            "name": "I/O",
            "description": "Template for testing input/output functions.",
            "tests": [
                {
                    "name": "test_function_1",
                    "description": "Tests function 1 with various inputs.",
                    "parameters": [
                        {
                            "name": "input1",
                            "description": "Description of input1",
                            "type": "string"
                        }
                    ]
                }, 
                ...
        """
        #1. Retrieve an instance of the template from the library
        template = TemplateLibrary.get_template(template_name, clean=True)
        if not template:
            raise ValueError(f"Template '{template_name}' not found.")
        
        #2. Prepare the main dictionary with basic template info
        template_data = {
            "template_name": template.template_name,
            "template_description": template.template_description,
            "tests": []
        }

        for test in template.get_tests().values():
            test_data = {
                "name": test.name,
                "description": test.description,
                "required_file": test.required_file,
                "parameters": []
            }
            for param in test.parameter_description:
                test_data["parameters"].append({
                    "name": param.name,
                    "description": param.description,
                    "type": param.type
                })
            template_data["tests"].append(test_data)

        return template_data
