import logging
import math
from typing import Dict, Optional, Sequence, List, overload

from autograder.models.abstract.ai_test_function import AiTestFunction
from autograder.models.abstract.criteria_tree_processer import CriteriaTreeProcesser
from autograder.models.abstract.test_function import EvaluationInput
from autograder.models.criteria_tree import (
    CategoryNode,
    SubjectNode,
    TestNode,
)
from autograder.models.dataclass.submission import EvaluationScope, SubmissionFile
from autograder.models.dataclass.test_result import TestResult
from autograder.models.result_tree import (
    CategoryResultNode,
    SubjectResultNode,
    TestResultNode,
)
from autograder.models.frozen import thaw
from autograder.models.evaluation_error import EvaluationError
from autograder.services.file_selection import select_files
from autograder.services.weights import normalized_sibling_weights

EXECUTION_CAPABILITIES = frozenset({"sandbox_execution", "http_network"})


class SubmissionGrader(CriteriaTreeProcesser):
    """Traverses a criteria tree for a single submission.

    All per-submission state lives here (and in each call's EvaluationInput);
    evaluator instances themselves are shared and stateless.
    """

    def __init__(
        self,
        submission_files: Dict[str, SubmissionFile],
        sandbox=None,
        submission_language=None,
        locale: str = "en",
        assessments: Optional[Dict[str, TestResult]] = None,
        evaluation_scope: Optional[EvaluationScope] = None,
    ):
        self.logger = logging.getLogger("SubmissionGrader")
        self.submission_files = submission_files
        self.sandbox = sandbox
        self.submission_language = submission_language
        self.locale = locale
        self.assessments = assessments
        self.evaluation_scope = evaluation_scope

    def __balance_nodes(
        self,
        nodes: Sequence[CategoryResultNode | SubjectResultNode | TestResultNode],
        factor: float,
    ) -> None:
        """Balance the weights of sibling nodes to sum to a target total (100 * factor)."""
        weights = normalized_sibling_weights([node.weight for node in nodes], factor)
        for node, weight in zip(nodes, weights):
            node.weight = weight

    @overload
    def __process_holder(self, holder: CategoryNode) -> CategoryResultNode: ...

    @overload
    def __process_holder(self, holder: SubjectNode) -> SubjectResultNode: ...

    def __process_holder(
        self,
        holder: CategoryNode | SubjectNode,
    ) -> CategoryResultNode | SubjectResultNode:
        """Process a category or subject node and create corresponding result node."""

        # Determine subjects and tests weight factors
        if holder.subjects and holder.tests:
            if holder.subjects_weight is None:
                raise ValueError(f"missing 'subjects_weight' for {holder.name}")
            subjects_factor = holder.subjects_weight / 100.0
            tests_factor = 1 - subjects_factor
        else:
            subjects_factor = 1.0
            tests_factor = 1.0

        # Process subjects
        subject_results = []
        if holder.subjects:
            subject_results = [
                self.process_subject(inner_subject)
                for inner_subject in holder.subjects
            ]
            self.__balance_nodes(subject_results, subjects_factor)

        # Process tests
        test_results = []
        if holder.tests:
            test_results = [
                self.process_test(test)
                for test in holder.tests
            ]
            self.__balance_nodes(test_results, tests_factor)

        # Create appropriate result node type
        if isinstance(holder, CategoryNode):
            return CategoryResultNode(
                name=holder.name,
                weight=holder.weight,
                subjects_weight=holder.subjects_weight,
                subjects=subject_results,
                tests=test_results,
            )
        return SubjectResultNode(
            name=holder.name,
            weight=holder.weight,
            subjects_weight=holder.subjects_weight,
            subjects=subject_results,
            tests=test_results,
        )

    def process_subject(self, subject: SubjectNode) -> SubjectResultNode:
        """Process a subject node from criteria tree and create result node."""
        return self.__process_holder(subject)

    def process_test(self, test: TestNode) -> TestResultNode:
        """Assess one criterion and create its result node."""
        function = test.test_function
        files = self.get_file_target(test)
        if isinstance(function, AiTestFunction):
            test_result = self.__assessment(test)
        else:
            evaluation = EvaluationInput(
                files=tuple(files),
                language=self.submission_language,
                locale=self.locale,
                # Only evaluators declaring execution receive the session.
                session=self.sandbox if test.capabilities & EXECUTION_CAPABILITIES else None,
            )
            # Each invocation receives an isolated copy of the canonical parameters.
            test_result = function.execute(evaluation, **thaw(test.parameters))
        if (not isinstance(test_result, TestResult) or isinstance(test_result.score, bool)
                or not isinstance(test_result.score, (int, float))
                or not math.isfinite(test_result.score) or not 0 <= test_result.score <= 100):
            raise EvaluationError("INVALID_EVALUATOR_RESULT", "An evaluator returned an invalid assessment.")
        return TestResultNode(
            criterion_id=test.criterion_id,
            evaluator=function.name,
            name=test.name,
            score=test_result.score,
            report=test_result.report,
            file_target=list(test.file_target) if test.file_target is not None else None,
            parameters=thaw(test.parameters),
            weight=test.weight,
        )

    def __assessment(self, test: TestNode) -> TestResult:
        """AI criteria take the provider batch's assessment for their criterion ID."""
        if self.assessments is None:
            raise EvaluationError("PROVIDER_UNAVAILABLE", "An AI assessment requires a host-supplied provider.", "provider")
        if test.criterion_id not in self.assessments:
            raise EvaluationError("MISSING_EVALUATOR_RESULT", "A required AI assessment was not returned.", "provider", True)
        return self.assessments[test.criterion_id]

    def get_file_target(self, test_node: TestNode) -> List[SubmissionFile]:
        """Use the same selection contract as batched AI assessment."""
        return select_files(test_node, self.submission_files, self.evaluation_scope, self.submission_language)

    def process_category(self, category: CategoryNode) -> CategoryResultNode:
        """Process a category node from criteria tree and create result node."""
        return self.__process_holder(category)
