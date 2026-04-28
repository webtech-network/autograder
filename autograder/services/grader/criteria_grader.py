import logging
from typing import Dict, Optional, Sequence, List, overload

from autograder.models.abstract.criteria_tree_processer import CriteriaTreeProcesser
from autograder.models.criteria_tree import (
    CategoryNode,
    SubjectNode,
    TestNode,
)
from autograder.models.dataclass.submission import SubmissionFile
from autograder.models.dataclass.test_result import TestResult
from autograder.models.result_tree import (
    CategoryResultNode,
    SubjectResultNode,
    TestResultNode,
)
from autograder.services.command_resolver import CommandResolver


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
        structural_analysis=None,
    ):
        self.logger = logging.getLogger("SubmissionGrader")
        self.submission_files = submission_files
        self.command_resolver = command_resolver
        self.sandbox = sandbox
        self.submission_language = submission_language
        self.locale = locale
        self.pre_computed_results = pre_computed_results
        self.structural_analysis = structural_analysis

    def __balance_nodes(
        self,
        nodes: Sequence[CategoryResultNode | SubjectResultNode | TestResultNode],
        factor: float,
    ) -> None:
        """Balance the weights of sibling nodes to sum to 100, scaled by factor."""
        if len(nodes) == 0:
            return

        total_weight = sum(node.weight for node in nodes) * factor

        if total_weight == 0:
            equal_weight = 100.0 / len(nodes)
            for node in nodes:
                node.weight = equal_weight
        elif total_weight != 100:
            scale_factor = 100.0 / total_weight
            for node in nodes:
                node.weight *= scale_factor

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
            if not holder.subjects_weight:
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

        # Inject the actual submission language so tests like forbidden_import
        # always operate on the real language rather than a config-time guess.
        if self.submission_language and 'submission_language' in test_params:
            test_params['submission_language'] = self.submission_language

        test_result = test.test_function.execute(
            files=file_target,
            sandbox=self.sandbox,
            locale=self.locale,
            pre_computed_results=self.pre_computed_results,
            structural_analysis=self.structural_analysis,
            submission_language=self.submission_language,
            **test_params,
        )
        return TestResultNode(
            name=test.name,
            test_node=test,
            score=test_result.score,
            report=test_result.report,
            parameters=test_result.parameters,
            weight=test.weight,
        )

    def get_file_target(self, test_node: TestNode) -> Optional[List[SubmissionFile]]:
        """Filter out the submission files strictly relevant to the current test node."""
        if not self.submission_files:
            return None

        if not test_node.file_target or test_node.file_target == ["all"]:
            return list(self.submission_files.values())

        target_files = []
        for file_name in self.submission_files:
            if file_name in test_node.file_target:
                target_files.append(self.submission_files[file_name])

        return target_files

    def process_category(self, category: CategoryNode) -> CategoryResultNode:
        """Process a category node from criteria tree and create result node."""
        return self.__process_holder(category)
