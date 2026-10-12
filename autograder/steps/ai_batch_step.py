import logging
from typing import Dict, List, Tuple

from autograder.models.abstract.step import Step
from autograder.models.criteria_tree import CriteriaTree, TestNode
from autograder.models.dataclass.step_result import StepName, StepResult, StepStatus
from autograder.models.dataclass.submission import SubmissionFile
from autograder.models.dataclass.test_result import TestResult
from autograder.models.pipeline_execution import PipelineExecution
from autograder.utils.executors.ai_executor import TestInput
from autograder.models.evaluation_error import EvaluationError
from autograder.services.file_selection import select_files

logger = logging.getLogger(__name__)


class AiBatchStep(Step):
    """
    Pipeline step that evaluates all AI-based tests in a single batched API call.

    This step runs **after** ``SandboxStep`` and **before** ``GradeStep``.
    It walks the criteria tree, collects every test whose function is an
    :class:`~autograder.models.abstract.ai_test_function.AiTestFunction`, builds
    each test's prompt via ``build_prompt()``, and sends one batched request to
    the host-supplied assessment provider.

    The results are stored as ``Dict[criterion_id, TestResult]`` in this step's
    ``StepResult.data``.  ``GradeStep`` retrieves them and passes them to
    ``GraderService`` as ``pre_computed_results`` so that each ``AiTestFunction``
    can return them directly from its ``execute()`` method — no further AI calls,
    no in-place mutation.

    If no AI test functions are found in the criteria tree the step exits
    immediately (empty dict result) and costs nothing.
    """

    @property
    def step_name(self) -> StepName:
        return StepName.AI_BATCH

    def _execute(self, pipeline_exec: PipelineExecution) -> PipelineExecution:
        """
        Collect all AI test functions from the criteria tree, send a single
        batched request to the AI model, and store the results.

        Args:
            pipeline_exec: PipelineExecution containing the built criteria tree
                and submission files from previous steps.

        Returns:
            PipelineExecution with a new AI_BATCH StepResult whose data is
            ``Dict[str, TestResult]`` (empty dict if no AI tests exist).
        """
        criteria_tree = pipeline_exec.get_built_criteria_tree()
        submission_files = pipeline_exec.submission.submission_files
        locale = pipeline_exec.locale

        ai_test_entries = self._collect_ai_tests(criteria_tree, submission_files, pipeline_exec.evaluation_scope, pipeline_exec.submission.language)

        if not ai_test_entries:
            logger.info("No AI test functions found; skipping AI batch request.")
            return pipeline_exec

        test_inputs: List[TestInput] = []
        all_files: Dict[str, str] = {name: submission_files[name].content for name in sorted(submission_files)}

        for test_func, files, params, criterion_id in ai_test_entries:
            prompt = test_func.build_prompt(files, locale=locale, context_files=[submission_files[name] for name in sorted(submission_files)], **params)
            if not criterion_id:
                raise EvaluationError("INVALID_DEFINITION", "An AI criterion has no identity.", "definition")
            test_inputs.append(TestInput(test_name=criterion_id, prompt=prompt))

        logger.info(
            "Sending AI batch request for %d test(s) (external_user_id=%s)",
            len(test_inputs),
            pipeline_exec.submission.user_id,
        )

        results: Dict[str, TestResult] = pipeline_exec.capabilities.ai.run(test_inputs, all_files, locale)
        if set(results) != {entry.test_name for entry in test_inputs}:
            raise EvaluationError("MISSING_EVALUATOR_RESULT", "A required AI assessment was not returned.", "provider", True)

        logger.info(
            "AI batch completed: %d/%d tests returned results.",
            len(results),
            len(test_inputs),
        )

        return pipeline_exec.add_step_result(
            StepResult(
                step=StepName.AI_BATCH,
                data=results,
                status=StepStatus.SUCCESS,
            )
        )

    # ------------------------------------------------------------------
    # Tree traversal helpers
    # ------------------------------------------------------------------

    def _collect_ai_tests(
        self,
        criteria_tree: CriteriaTree,
        submission_files: Dict[str, SubmissionFile],
        evaluation_scope=None,
        submission_language=None,
    ) -> List[Tuple]:
        """
        Walk the full criteria tree and return a list of
        ``(AiTestFunction, files, params)`` tuples for every AI test found.
        """
        entries: List[Tuple] = []
        self._walk(criteria_tree.base, submission_files, entries, evaluation_scope, submission_language)
        if criteria_tree.bonus:
            self._walk(criteria_tree.bonus, submission_files, entries, evaluation_scope, submission_language)
        if criteria_tree.penalty:
            self._walk(criteria_tree.penalty, submission_files, entries, evaluation_scope, submission_language)
        return entries

    def _walk(self, node, submission_files: Dict[str, SubmissionFile], entries: list, evaluation_scope=None, submission_language=None) -> None:
        """Recursively traverse a node and collect AI test entries."""
        # Local import avoids a circular-dependency at module load time.
        from autograder.models.abstract.ai_test_function import AiTestFunction

        if isinstance(node, TestNode):
            if isinstance(node.test_function, AiTestFunction):
                files = select_files(node, submission_files, evaluation_scope, submission_language)
                entries.append((node.test_function, files, dict(node.parameters or {}), node.criterion_id))
            return

        for test in getattr(node, "tests", []):
            self._walk(test, submission_files, entries, evaluation_scope, submission_language)
        for subject in getattr(node, "subjects", []):
            self._walk(subject, submission_files, entries, evaluation_scope, submission_language)
