import logging

from typing import Dict, Optional, Sequence, List, overload
from autograder.services.command_resolver import CommandResolver
from autograder.models.criteria_tree import (
    CriteriaTree,
    CategoryNode,
    SubjectNode,
    TestNode,
)
from autograder.models.dataclass.submission import SubmissionFile
from autograder.models.dataclass.test_result import TestResult
from autograder.models.result_tree import (
    ResultTree,
    RootResultNode,
    CategoryResultNode,
    SubjectResultNode,
    TestResultNode,
)


class GraderService:
    """Service responsible for orchestrating the grading process using a configured criteria tree."""

    def __init__(self):
        self.logger = logging.getLogger("GraderService")
        self._command_resolver = CommandResolver()

    def grade_from_tree(
        self,
        criteria_tree: CriteriaTree,
        submission_files: Dict[str, SubmissionFile],
        sandbox=None,
        submission_language=None,
        locale: str = "en",
        pre_computed_results: Optional[Dict[str, TestResult]] = None,
    ) -> ResultTree:
        """Traverse the generic built criteria tree to resolve inputs, grades and report to ResultTree."""
        base_result = self.process_category(
            criteria_tree.base,
            submission_files=submission_files,
            sandbox=sandbox,
            submission_language=submission_language,
            locale=locale,
            pre_computed_results=pre_computed_results,
        )
        root = RootResultNode(name="root", base=base_result)

        if criteria_tree.bonus:
            bonus_result = self.process_category(
                criteria_tree.bonus,
                submission_files=submission_files,
                sandbox=sandbox,
                submission_language=submission_language,
                locale=locale,
                pre_computed_results=pre_computed_results,
            )
            root.bonus = bonus_result

        if criteria_tree.penalty:
            penalty_result = self.process_category(
                criteria_tree.penalty,
                submission_files=submission_files,
                sandbox=sandbox,
                submission_language=submission_language,
                locale=locale,
                pre_computed_results=pre_computed_results,
            )
            root.penalty = penalty_result

        return ResultTree(root)

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
        submission_files: Dict[str, SubmissionFile],
        sandbox=None,
        submission_language=None,
        locale: str = "en",
        pre_computed_results: Optional[Dict[str, TestResult]] = None,
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
                self.process_subject(
                    inner_subject,
                    submission_files=submission_files,
                    sandbox=sandbox,
                    submission_language=submission_language,
                    locale=locale,
                    pre_computed_results=pre_computed_results,
                )
                for inner_subject in holder.subjects
            ]
            self.__balance_nodes(subject_results, subjects_factor)

        # Process tests
        test_results = []
        if holder.tests:
            test_results = [
                self.process_test(
                    test,
                    submission_files=submission_files,
                    sandbox=sandbox,
                    submission_language=submission_language,
                    locale=locale,
                    pre_computed_results=pre_computed_results,
                )
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

    def process_subject(
        self,
        subject: SubjectNode,
        submission_files: Dict[str, SubmissionFile],
        sandbox=None,
        submission_language=None,
        locale: str = "en",
        pre_computed_results: Optional[Dict[str, TestResult]] = None,
    ) -> SubjectResultNode:
        """Process a subject node from criteria tree and create result node."""
        return self.__process_holder(
            subject,
            submission_files=submission_files,
            sandbox=sandbox,
            submission_language=submission_language,
            locale=locale,
            pre_computed_results=pre_computed_results,
        )

    def process_test(
        self,
        test: TestNode,
        submission_files: Optional[Dict[str, SubmissionFile]] = None,
        sandbox=None,
        submission_language=None,
        locale: str = "en",
        pre_computed_results: Optional[Dict[str, TestResult]] = None,
    ) -> TestResultNode:
        """Execute a test and create a test result node.

        Resolves `program_command` in-place before calling execute() so that
        test functions always receive a finalized string command.  Every key in
        ``test_params`` is a declared parameter of the test function.

        ``pre_computed_results`` is intentionally forwarded to
        ``test_function.execute()`` as an extra kwarg so that
        :class:`~autograder.models.abstract.ai_test_function.AiTestFunction`
        implementations can return the pre-computed result without a further API call.
        Regular test functions that do not declare this parameter must accept
        ``**kwargs`` or ignore it.
        """
        file_target = self.get_file_target(test, submission_files=submission_files)

        # Shallow-copy parameters so we don't mutate the original TestNode.
        test_params = dict(test.parameters or {})

        # Resolve program_command eagerly when the language is known.
        if submission_language and 'program_command' in test_params:
            raw_command = test_params['program_command']
            resolved = self._command_resolver.resolve_command(
                raw_command, submission_language
            )
            test_params['program_command'] = resolved

        # Inject the actual submission language so tests like forbidden_import
        # always operate on the real language rather than a config-time guess.
        if submission_language and 'submission_language' in test_params:
            test_params['submission_language'] = submission_language

        test_result = test.test_function.execute(
            files=file_target,
            sandbox=sandbox,
            locale=locale,
            pre_computed_results=pre_computed_results,
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


    def get_file_target(
        self,
        test_node: TestNode,
        submission_files: Optional[Dict[str, SubmissionFile]],
    ) -> Optional[List[SubmissionFile]]:
        """Filter out the submission files strictly relevant to the current test node.

        When no file_target is specified, returns all submission files so that
        tests like forbidden_import can scan the actual submitted file regardless
        of language.
        """
        if not submission_files:
            return None

        if not test_node.file_target or test_node.file_target == ["all"]:
            return list(submission_files.values())

        target_files = []
        for file_name in submission_files:
            if file_name in test_node.file_target:
                target_files.append(submission_files[file_name])

        return target_files

    def process_category(
        self,
        category: CategoryNode,
        submission_files: Dict[str, SubmissionFile],
        sandbox=None,
        submission_language=None,
        locale: str = "en",
        pre_computed_results: Optional[Dict[str, TestResult]] = None,
    ) -> CategoryResultNode:
        """Process a category node from criteria tree and create result node."""
        return self.__process_holder(
            category,
            submission_files=submission_files,
            sandbox=sandbox,
            submission_language=submission_language,
            locale=locale,
            pre_computed_results=pre_computed_results,
        )
