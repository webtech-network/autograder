import logging
import math
from typing import Dict, Optional, Sequence, List, overload

from autograder.models.abstract.criteria_tree_processer import CriteriaTreeProcesser
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
from autograder.services.command_resolver import CommandResolver
from autograder.models.evaluation_error import EvaluationError
from autograder.services.file_selection import select_files
from autograder.services.structural_analysis import StructuralAnalysisCache
from autograder.services.weights import normalized_sibling_weights


class SubmissionGrader(CriteriaTreeProcesser):
    """
    Stateful grader responsible for traversing a criteria tree for a single submission.
    Implements the CriteriaTreeProcesser interface.
    """

    def __init__(
        self,
        submission_files: Dict[str, SubmissionFile],
        command_resolver: CommandResolver,
        sandbox=None,
        submission_language=None,
        locale: str = "en",
        pre_computed_results: Optional[Dict[str, TestResult]] = None,
        evaluation_scope: Optional[EvaluationScope] = None,
    ):
        self.logger = logging.getLogger("SubmissionGrader")
        self.submission_files = submission_files
        self.command_resolver = command_resolver
        self.sandbox = sandbox
        self.submission_language = submission_language
        self.locale = locale
        self.pre_computed_results = pre_computed_results
        self.structural_analysis = StructuralAnalysisCache()
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
        """Execute a test and create a test result node."""
        file_target = self.get_file_target(test)

        # Shallow-copy parameters so we don't mutate the original TestNode.
        test_params = dict(test.parameters or {})

        # Resolve program_command eagerly when the language is known.
        if self.submission_language and 'program_command' in test_params:
            raw_command = test_params['program_command']
            resolved = self.command_resolver.resolve_command(
                raw_command, self.submission_language
            )
            test_params['program_command'] = resolved

        # Ensure submission_language is passed only once.
        # Runtime language always takes precedence over config-specified language.
        config_submission_language = test_params.pop('submission_language', None)
        effective_submission_language = (
            self.submission_language
            if self.submission_language is not None
            else config_submission_language
        )
        test_params.pop("evaluation_scope", None)
        test_params.pop("file_metadata", None)
        test_params.pop("criterion_id", None)

        file_metadata = {
            sub_file.filename: sub_file.metadata
            for sub_file in file_target or []
        }

        test_result = test.test_function.execute(
            files=file_target,
            sandbox=self.sandbox,
            locale=self.locale,
            pre_computed_results=self.pre_computed_results,
            structural_analysis=self.structural_analysis,
            submission_language=effective_submission_language,
            evaluation_scope=self.evaluation_scope,
            file_metadata=file_metadata,
            context_files=[self.submission_files[name] for name in sorted(self.submission_files)],
            criterion_id=test.criterion_id,
            **test_params,
        )
        if (not isinstance(test_result, TestResult) or isinstance(test_result.score, bool)
                or not isinstance(test_result.score, (int, float))
                or not math.isfinite(test_result.score) or not 0 <= test_result.score <= 100):
            raise EvaluationError("INVALID_EVALUATOR_RESULT", "An evaluator returned an invalid assessment.")
        return TestResultNode(
            criterion_id=test.criterion_id,
            evaluator=test.test_function.name,
            name=test.name,
            test_node=test,
            score=test_result.score,
            report=test_result.report,
            parameters=dict(test.parameters or {}),
            weight=test.weight,
        )

    def get_file_target(self, test_node: TestNode) -> List[SubmissionFile]:
        """Use the same selection contract as batched AI assessment."""
        return select_files(test_node, self.submission_files, self.evaluation_scope, self.submission_language)

    def process_category(self, category: CategoryNode) -> CategoryResultNode:
        """Process a category node from criteria tree and create result node."""
        return self.__process_holder(category)
