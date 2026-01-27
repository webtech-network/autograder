from autograder.models.dataclass.pipeline_execution import PipelineExecution
from autograder.services.template_library_service import TemplateLibraryService
from autograder.models.abstract.step import Step


class TemplateLoaderStep(Step):
    def __init__(self, template_name: str, custom_template = None):
        self._template_name = template_name
        self._custom_template = custom_template
        self._template_service = TemplateLibraryService()

    def execute(self, input: PipelineExecution) -> PipelineExecution:
        if self._custom_template:
            return self._template_service.load_custom_template(self._custom_template) #TODO: Implement Custom Template Loading with Sandboxed Env
        else:
            return self._template_service.load_builtin_template(self._template_name) # Load built-in template similar to custom to avoid code duplication


