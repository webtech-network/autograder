import logging
from typing import Union, List, Optional

from autograder.models.dataclass.step_result import StepResult, StepName, StepStatus
from autograder.models.pipeline_execution import PipelineExecution
from autograder.services.template_library_service import TemplateLibraryService
from autograder.models.abstract.step import Step

logger = logging.getLogger(__name__)


class TemplateLoaderStep(Step):
    """
    Step that loads one or more grading templates, which contain test functions 
    and helper code used for grading.
    """
    def __init__(self, template_name: Union[str, List[str]], custom_template = None):
        """
        Initialize the template loader step.
        """
        if isinstance(template_name, str):
            self._template_names = [name.strip() for name in template_name.split(",")]
        else:
            self._template_names = template_name
        self._custom_template = custom_template
        self._template_service = TemplateLibraryService.get_instance()

    @property
    def step_name(self) -> StepName:
        return StepName.LOAD_TEMPLATE

    def _execute(self, pipeline_exec: PipelineExecution) -> PipelineExecution:
        """
        Load the grading templates and return them as part of the step result.
        """
        templates = []
        
        if self._custom_template:
            logger.info("Loading custom template (external_user_id=%s)", pipeline_exec.submission.user_id)
            template = self._template_service.load_custom_template(self._custom_template)
            templates.append(template)
        else:
            for name in self._template_names:
                logger.info(
                    "Loading built-in template: template=%s (external_user_id=%s)",
                    name,
                    pipeline_exec.submission.user_id,
                )
                template = self._template_service.load_builtin_template(name)
                templates.append(template)
        
        logger.info(
            "Templates loaded successfully: count=%d (external_user_id=%s)",
            len(templates),
            pipeline_exec.submission.user_id,
        )
        return pipeline_exec.add_step_result(
            StepResult(
                step=StepName.LOAD_TEMPLATE,
                data=templates,
                status=StepStatus.SUCCESS
            )
        )
