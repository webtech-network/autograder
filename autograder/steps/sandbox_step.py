"""Acquire the session requested by the execution's single requirements decision."""
from autograder.models.abstract.step import Step
from autograder.models.dataclass.step_result import StepName, StepResult
from autograder.models.evaluation_error import EvaluationError


class SandboxStep(Step):
    @property
    def step_name(self):
        return StepName.SANDBOX

    def _execute(self, pipeline_exec):
        providers = pipeline_exec.capabilities
        required = pipeline_exec.requirements.capabilities
        acquire = providers.server_execution if "http_network" in required else providers.execution
        try:
            # Attach before staging: ownership transfers on return from acquire.
            pipeline_exec.sandbox = acquire(pipeline_exec.submission.language)
            pipeline_exec.sandbox.prepare_workdir(pipeline_exec.submission.submission_files)
        except Exception as exc:
            raise EvaluationError("CAPABILITY_UNAVAILABLE", "The execution environment is unavailable.",
                                  "capability", True) from exc
        return pipeline_exec.add_step_result(StepResult.success(self.step_name, pipeline_exec.sandbox))
