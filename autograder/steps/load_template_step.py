from autograder.models.abstract.template import Template
from autograder.models.dataclass.step_result import StepResult, StepName, StepStatus
from autograder.models.pipeline_execution import PipelineExecution
from autograder.models.abstract.step import Step


class TemplateLoaderStep(Step):
    """Attach the trusted instances already resolved and validated by compilation."""

    def __init__(self, templates: list[Template]):
        self._templates = list(templates)

    @property
    def step_name(self) -> StepName:
        return StepName.LOAD_TEMPLATE

    def _execute(self, pipeline_exec: PipelineExecution) -> PipelineExecution:
        return pipeline_exec.add_step_result(
            StepResult(
                step=StepName.LOAD_TEMPLATE,
                data=list(self._templates),
                status=StepStatus.SUCCESS
            )
        )
