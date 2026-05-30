
from typing import Optional

from autograder.models.abstract.test_function import TestFunction
from autograder.models.dataclass.test_result import TestResult
from autograder.translations import t
from sandbox_manager.sandbox_container import SandboxContainer
from sandbox_manager.models.sandbox_models import ResponseCategory


class BaseExecutionTest(TestFunction):
    """
    Abstract base class for tests that involve running a student's code
    in a sandbox and handling basic execution results (timeouts, crashes).
    """

    def run_sandbox_execution(self, sandbox: SandboxContainer, inputs: list = None,
                              program_command: Optional[str] = None):
        """
        Executes the command inside the sandbox.
        `program_command` must already be a resolved string (or None).
        Returns the raw `output` from the sandbox run.
        """
        # Run with a pre-resolved command
        if program_command:
            safe_inputs = inputs if inputs is not None else []
            return sandbox.run_commands(safe_inputs, program_command=program_command)

        if inputs is None:
            raise ValueError("inputs parameter is required if no program_command is provided")
        command = ' '.join(inputs) if isinstance(inputs, list) else str(inputs)
        return sandbox.run_command(command)

    def check_for_base_errors(self, output, **kwargs) -> TestResult:
        """
        Checks for Timeout, Compilation Error, or Runtime Error in the sandbox output.
        Returns a TestResult with score 0.0 if an error is found, or None if successful.
        """
        if output.category == ResponseCategory.TIMEOUT:
            return TestResult(
                test_name=self.name,
                score=0.0,
                report=t("io.execution.timeout", locale=kwargs.get("locale"), time=output.execution_time)
            )

        if output.category == ResponseCategory.COMPILATION_ERROR:
            return TestResult(
                test_name=self.name,
                score=0.0,
                report=t("io.execution.compilation_error", locale=kwargs.get("locale"), error=output.stderr)
            )

        if output.category == ResponseCategory.RUNTIME_ERROR:
            return TestResult(
                test_name=self.name,
                score=0.0,
                report=t("io.execution.runtime_error", locale=kwargs.get("locale"), error=output.stderr)
            )

        if output.category == ResponseCategory.SYSTEM_ERROR:
            return TestResult(
                test_name=self.name,
                score=0.0,
                report=t("io.execution.system_error", locale=kwargs.get("locale"), error=output.stderr)
            )

        return None
