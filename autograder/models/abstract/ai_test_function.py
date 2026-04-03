from abc import abstractmethod
from typing import Dict, List, Optional

from autograder.models.abstract.test_function import TestFunction
from autograder.models.dataclass.submission import SubmissionFile
from autograder.models.dataclass.test_result import TestResult
from sandbox_manager.sandbox_container import SandboxContainer


class AiTestFunction(TestFunction):
    """
    Abstract base class for test functions whose evaluation is delegated to an AI model.

    Subclasses must implement ``build_prompt()`` to describe what the AI should evaluate.
    Subclasses must NOT override ``execute()``; the base implementation handles both the
    normal pipeline path (pre-computed results injected by ``AiBatchStep``) and a fallback
    single-call path (useful for direct testing without a full pipeline).
    """

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
        sandbox: Optional[SandboxContainer],
        **kwargs,
    ) -> TestResult:
        """
        Return the pre-computed AI result or fall back to a single API call.

        When ``AiBatchStep`` has already produced results, ``GraderService`` injects
        them as the ``pre_computed_results`` kwarg. This method looks up its own
        test name in that dict and returns the result directly. If the dict is
        absent (standalone usage), it falls back to ``_run_single()``.
        """
        pre_computed: Optional[Dict[str, TestResult]] = kwargs.get("pre_computed_results")
        if pre_computed is not None and self.name in pre_computed:
            return pre_computed[self.name]

        return self._run_single(files, **kwargs)

    def _run_single(
        self,
        files: Optional[List[SubmissionFile]],
        **kwargs,
    ) -> TestResult:
        """
        Fallback: make a single AI API call for just this one test.

        Used when ``pre_computed_results`` is not available (e.g. unit tests,
        standalone runners, or pipelines that do not include ``AiBatchStep``).
        """
        # Local import to avoid circular dependencies.
        from autograder.utils.executors.ai_executor import AiExecutor, TestInput

        locale: str = kwargs.get("locale", "en")
        prompt = self.build_prompt(files, **kwargs)
        submission_files = {f.filename: f.content for f in files} if files else {}
        test_inputs = [TestInput(test_name=self.name, prompt=prompt)]

        results = AiExecutor().run(test_inputs, submission_files, locale)
        return results.get(
            self.name,
            TestResult(
                test_name=self.name,
                score=0,
                report="AI evaluation produced no result.",
                subject_name="",
                parameters={},
            ),
        )
