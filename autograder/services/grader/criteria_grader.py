import logging
from typing import Mapping, Sequence, overload

from autograder.models.abstract.criteria_tree_processer import CriteriaTreeProcesser
from autograder.models.criteria_tree import (
    CategoryNode,
    SubjectNode,
    TestNode,
)
from autograder.models.dataclass.test_result import TestResult
from autograder.models.result_tree import (
    CategoryResultNode,
    SubjectResultNode,
    TestResultNode,
)
from autograder.models.frozen import thaw
from autograder.models.evaluation_error import EvaluationError
from autograder.services.weights import normalized_sibling_weights


class SubmissionGrader(CriteriaTreeProcesser):
    """Combines one submission's assessed results into a weighted result tree.

    The grader executes no evaluator: ``assess_criteria`` already produced one
    validated result per criterion ID (ordinary and AI alike).
    """

    def __init__(self, results: Mapping[str, TestResult]):
        self.logger = logging.getLogger("SubmissionGrader")
        self.results = results

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
        """Place one criterion's assessed result in the tree."""
        if test.criterion_id not in self.results:
            raise EvaluationError("MISSING_EVALUATOR_RESULT", "A required assessment was not produced.")
        test_result = self.results[test.criterion_id]
        return TestResultNode(
            criterion_id=test.criterion_id,
            evaluator=test.test_function.name,
            name=test.name,
            score=test_result.score,
            report=test_result.report,
            file_target=list(test.file_target) if test.file_target is not None else None,
            parameters=thaw(test.parameters),
            weight=test.weight,
        )

    def process_category(self, category: CategoryNode) -> CategoryResultNode:
        """Process a category node from criteria tree and create result node."""
        return self.__process_holder(category)
