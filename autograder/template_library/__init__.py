"""Template library package exports."""

from autograder.template_library.web_dev import WebDevTemplate
from autograder.template_library.api_testing import ApiTestingTemplate
from autograder.template_library.input_output import InputOutputTemplate

__all__ = [
    "WebDevTemplate",
    "ApiTestingTemplate",
    "InputOutputTemplate",
]
