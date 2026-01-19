from autograder.models.abstract.template import Template
from autograder.template_library.web_dev import WebDevTemplate
from autograder.template_library.api_testing import ApiTestingTemplate
from autograder.template_library.input_output import InputOutputTemplate
from autograder.template_library.essay_grader import EssayGraderTemplate

class TemplateLibraryService:
    def __init__(self):
        pass

    def start_template(self, template_name: str) -> Template:
        """Initialize and return the template class based on the template name.
           If template requires sandboxing, it creates a sandboxed instance.
        """
        pass

    def get_template_info(self, template_name: str) -> dict:
        """Return metadata about the template."""
        pass


