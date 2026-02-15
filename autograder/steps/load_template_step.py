from autograder.models.dataclass.step_result import StepResult, StepName, StepStatus
from autograder.models.pipeline_execution import PipelineExecution
from autograder.services.template_library_service import TemplateLibraryService
from autograder.models.abstract.step import Step


class TemplateLoaderStep(Step):
    """
    Step that loads a grading template, which contains test functions and helper code used for grading.
    It can load either a built-in template from the library or a custom template provided by the user.
    If the template is custom, it should be loaded in a sandboxed environment to ensure security and isolation.
    """
    def __init__(self, template_name: str, custom_template = None):
        """
        Initialize the template loader step.
        """
        self._template_name = template_name
        self._custom_template = custom_template
        self._template_service = TemplateLibraryService.get_instance()

    def execute(self, input: PipelineExecution) -> PipelineExecution:
        """
        Load the grading template, either built-in or custom, and return it as part of the step result.
        """
        try:
            if self._custom_template:
                template = self._template_service.load_custom_template(self._custom_template) #TODO: Implement Custom Template Loading with Sandboxed Env
            else:
                template = self._template_service.load_builtin_template(self._template_name) # Load built-in template similar to custom to avoid code duplication
            return input.add_step_result(
                StepResult(
                    step=StepName.LOAD_TEMPLATE,
                    data=template,
                    status=StepStatus.SUCCESS
                )
            )
        except Exception as e:
            return input.add_step_result(
                StepResult(
                    step=StepName.LOAD_TEMPLATE,
                    data=None,
                    status=StepStatus.FAIL,
                    error=f"Failed to load template: {str(e)}"
                )
            )



