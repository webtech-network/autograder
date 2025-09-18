import importlib.util
import inspect
from autograder.builder.models.template import Template

class TemplateLibrary:
    @staticmethod
    def get_template(template_name: str, custom_template_path: str = None):
        if template_name == "custom":
            if not custom_template_path:
                raise ValueError("Custom template path must be provided for 'custom' template type.")
            return TemplateLibrary._load_custom_template(custom_template_path)

        if template_name == "web dev":
            from autograder.builder.template_library.templates.web_dev import WebDevTemplate
            return WebDevTemplate()
        if template_name == "api":
            from autograder.builder.template_library.templates.api_testing import ApiTestingTemplate
            return ApiTestingTemplate()
        if template_name == "essay":
            from autograder.builder.template_library.templates.essay_grader import EssayGraderTemplate
            return EssayGraderTemplate()
        if template_name == "I/O":
            from autograder.builder.template_library.templates.input_output import InputOutputTemplate
            return InputOutputTemplate()
        else:
            raise ValueError(f"Template '{template_name}' not found.")

    @staticmethod
    def _load_custom_template(file_path: str):
        spec = importlib.util.spec_from_file_location("custom_template", file_path)
        custom_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(custom_module)

        for name, obj in inspect.getmembers(custom_module):
            if inspect.isclass(obj) and issubclass(obj, Template) and obj is not Template:
                return obj() # Instantiate and return the custom template

        raise ImportError(f"No class inheriting from 'Template' found in {file_path}")