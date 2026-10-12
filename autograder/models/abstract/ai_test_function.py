from abc import abstractmethod
from typing import Dict, List, Optional

from autograder.models.abstract.test_function import TestFunction
from autograder.models.dataclass.submission import SubmissionFile
from autograder.models.dataclass.test_result import TestResult

from autograder.models.execution import ExecutionSession
from autograder.models.evaluation_error import EvaluationError


class AiTestFunction(TestFunction):
    """
    Abstract base class for test functions whose evaluation is delegated to an AI model.

    Subclasses must implement ``build_prompt()`` to describe what the AI should evaluate.
    Subclasses must NOT override ``execute()``; the base implementation handles both the
    normal pipeline path (pre-computed results injected by ``AiBatchStep``) with results supplied by the host assessment provider.
    """

    required_capabilities = ("ai_provider",)

    @abstractmethod
    def build_prompt(self, files: Optional[List[SubmissionFile]], **kwargs) -> str:
        """
        Build the AI evaluation prompt for this test.

        Args:
            files: The submission files relevant to this test (already filtered by
                ``file_target``), or ``None`` if the test does not require file content.
            **kwargs: Any test parameters declared in the criteria configuration.

        Returns:
            The prompt text that will be sent to the AI model.
        """

    def execute(
        self,
        files: Optional[List[SubmissionFile]],
        sandbox: Optional[ExecutionSession],
        *args,
        **kwargs,
    ) -> TestResult:
        """
        Return the required pre-computed AI result.

        When ``AiBatchStep`` has already produced results, ``GraderService`` injects
        them as the ``pre_computed_results`` kwarg. This method looks up its own
        criterion ID in that dict and returns the result directly. If the dict is
        absent (standalone usage), it falls back to ``_run_single()``.
        """
        # args is not used in AI tests as parameters are in kwargs
        _ = args
        pre_computed: Optional[Dict[str, TestResult]] = kwargs.get("pre_computed_results")
        criterion_id = kwargs.get("criterion_id")
        if not criterion_id:
            raise EvaluationError("INVALID_DEFINITION", "An AI criterion has no identity.", "definition")
        if pre_computed is not None:
            if criterion_id not in pre_computed:
                raise EvaluationError("MISSING_EVALUATOR_RESULT", "A required AI assessment was not returned.", "provider", True)
            return pre_computed[criterion_id]

        raise EvaluationError("PROVIDER_UNAVAILABLE", "An AI assessment requires a host-supplied provider.", "provider")
