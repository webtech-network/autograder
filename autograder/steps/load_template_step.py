import logging
from typing import List, Union

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
    def __init__(self, template_name: Union[str, List[str], None], custom_template=None):
        """
        Initialize the template loader step.
        """
        self._template_names = self._normalize_template_names(template_name)
        self._custom_template = custom_template
        self._template_service = TemplateLibraryService.get_instance()
        if not self._custom_template and not self._template_names:
            raise ValueError(
                "template_name must contain at least one non-empty template identifier."
            )

    @staticmethod
    def _normalize_template_names(template_name: Union[str, List[str], None]) -> List[str]:
        if template_name is None:
            return []

        if isinstance(template_name, str):
            raw_names = template_name.split(",")
        elif isinstance(template_name, list):
            raw_names = template_name
        else:
            raise ValueError(
                "template_name must be a comma-separated string or a list of strings."
            )

        normalized: List[str] = []
        for name in raw_names:
            if not isinstance(name, str):
                raise ValueError("template_name entries must be strings.")
            stripped = name.strip()
            if stripped:
                normalized.append(stripped)
        return normalized

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
