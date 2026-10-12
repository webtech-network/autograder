"""Prepare selected typed commands and fixtures after pure input validation."""
from autograder.models.abstract.step import Step
from autograder.models.dataclass.step_result import StepName, StepResult
from autograder.models.evaluation_error import EvaluationError
from sandbox_manager.models.sandbox_models import ResponseCategory


class PreFlightStep(Step):
    def __init__(self, preparation):
        self.preparation = preparation

    @property
    def step_name(self):
        return StepName.PRE_FLIGHT

    def _execute(self, pipeline_exec):
        session = pipeline_exec.sandbox
        try:
            for fixture in self.preparation.fixtures:
                content = pipeline_exec.capabilities.fixtures(fixture.reference)
                if not isinstance(content, bytes):
                    raise TypeError("Fixture providers must return bytes")
                session.stage_fixture(fixture.path, content, fixture.read_only)
            for command in pipeline_exec.requirements.preparation.setup_commands:
                result = session.run_command(command.command)
                if result.category == ResponseCategory.SYSTEM_ERROR:
                    raise EvaluationError("SANDBOX_ERROR", "The execution environment could not prepare the submission.", "capability", True)
                if result.category != ResponseCategory.SUCCESS:
                    raise EvaluationError("PREPARATION_FAILED", "A required setup command failed.", "submission")
            if "http_network" in pipeline_exec.requirements.capabilities:
                session.start_server()
                session.wait_ready()
        except EvaluationError:
            raise
        except Exception as exc:
            raise EvaluationError("PREPARATION_ERROR", "Assignment preparation could not complete.", "capability", True) from exc
        return pipeline_exec.add_step_result(StepResult.success(self.step_name, None))
