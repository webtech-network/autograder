import logging
from typing import Optional

from autograder.models.dataclass.step_result import StepResult, StepName, StepStatus
from autograder.models.pipeline_execution import PipelineExecution
from autograder.services.template_library_service import TemplateLibraryService
from autograder.models.abstract.step import Step

logger = logging.getLogger(__name__)


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

    @property
    def step_name(self) -> StepName:
        return StepName.LOAD_TEMPLATE

    def _execute(self, pipeline_exec: PipelineExecution, locale: Optional[str] = None) -> PipelineExecution:
        """
        Load the grading template, either built-in or custom, and return it as part of the step result.
        """
        if self._custom_template:
            logger.info("Loading custom template (external_user_id=%s)", pipeline_exec.submission.user_id)
            template = self._template_service.load_custom_template(self._custom_template) #TODO: Implement Custom Template Loading with Sandboxed Env
        else:
            logger.info(
                "Loading built-in template: template=%s (external_user_id=%s)",
                self._template_name,
                pipeline_exec.submission.user_id,
            )
            template = self._template_service.load_builtin_template(self._template_name) # Load built-in template similar to custom to avoid code duplication
        
        logger.info(
            "Template loaded successfully: template=%s (external_user_id=%s)",
            self._template_name,
            pipeline_exec.submission.user_id,
        )
        return pipeline_exec.add_step_result(
            StepResult(
                step=StepName.LOAD_TEMPLATE,
                data=template,
                status=StepStatus.SUCCESS
            )
        )



