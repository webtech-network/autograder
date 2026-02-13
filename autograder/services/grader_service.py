import logging

from typing import Dict, Optional, Sequence, List
from autograder.models.criteria_tree import CriteriaTree, CategoryNode, SubjectNode, TestNode
from autograder.models.dataclass.submission import SubmissionFile
from autograder.models.result_tree import (
    ResultTree,
    RootResultNode,
    CategoryResultNode,
    SubjectResultNode,
    TestResultNode
)



class GraderService():
    def __init__(self):
        self.logger = logging.getLogger("GraderService")
        self.__submission_files = None
        self._sandbox = None

    def set_sandbox(self, sandbox):
        self._sandbox = sandbox

    def has_sandbox(self) -> bool:
        return self._sandbox is not None

    def grade_from_tree(
        self,
        criteria_tree: CriteriaTree,
        submission_files: Dict[str,SubmissionFile],
    ) -> ResultTree:
        self.__submission_files = submission_files

        # Create root node with category results
        root = RootResultNode(name="root")

        # Process base category (required)
        base_result = self.process_category(criteria_tree.base)
        root.base = base_result

        # Process bonus category (optional)
        if criteria_tree.bonus:
            bonus_result = self.process_category(criteria_tree.bonus)
            root.bonus = bonus_result

        # Process penalty category (optional)
        if criteria_tree.penalty:
            penalty_result = self.process_category(criteria_tree.penalty)
            root.penalty = penalty_result

        result_tree = ResultTree(root)

        # Handle AI executor batch if needed
        # Note: For tree-based grading, the template is embedded in test nodes
        first_test = self.__find_first_test(criteria_tree.base)
        if first_test and hasattr(first_test, "test_function"):
            test_func = first_test.test_function
            if hasattr(test_func, "executor") and test_func.executor:
                self.logger.info("Executing AI batch requests")
                test_func.executor.stop()

        return result_tree

    def __balance_nodes(
        self,
        nodes: Sequence[CategoryResultNode | SubjectResultNode | TestResultNode],
        factor: float
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

    def __process_holder(
        self,
        holder: CategoryNode | SubjectNode
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
                self.process_subject(inner_subject) for inner_subject in holder.subjects
            ]
            self.__balance_nodes(subject_results, subjects_factor)

        # Process tests
        test_results = []
        if holder.tests:
            test_results = [self.process_test(test) for test in holder.tests]
            self.__balance_nodes(test_results, tests_factor)

        # Create appropriate result node type
        if isinstance(holder, CategoryNode):
            return CategoryResultNode(
                name=holder.name,
                weight=holder.weight,
                subjects=subject_results,
                tests=test_results
            )
        else:  # SubjectNode
            return SubjectResultNode(
                name=holder.name,
                weight=holder.weight,
                subjects=subject_results,
                tests=test_results
            )

    def process_subject(self, subject: SubjectNode) -> SubjectResultNode:
        """Process a subject node from criteria tree and create result node."""
        return self.__process_holder(subject)

    def process_test(self, test: TestNode) -> TestResultNode:
        """Execute a test and create a test result node."""
        file_target = self.get_file_target(test)
        test_result = test.test_function.execute(
            files=file_target,
            sandbox=self._sandbox,
            **(test.parameters or {})
        )
        return TestResultNode(
            name=test.name,
            test_node=test,
            score=test_result.score,
            report=test_result.report,
            parameters=test_result.parameters
        )

    def get_file_target(self,test_node: TestNode) -> Optional[List[SubmissionFile]] :
        if not test_node.file_target:
            return None
        target_files = []
        for file_name in self.__submission_files:
            if file_name in test_node.file_target:
                target_files.append(self.__submission_files[file_name])
        return target_files

    def process_category(self, category: CategoryNode) -> CategoryResultNode:
        """Process a category node from criteria tree and create result node."""
        return self.__process_holder(category)

    def __find_first_test(self, node: CategoryNode | SubjectNode) -> Optional[TestNode]:
        """Find the first test node in the tree."""
        if isinstance(node, TestNode):
            return node

        if hasattr(node, "tests") and node.tests:
            return node.tests[0]

        if hasattr(node, "subjects") and node.subjects:
            for subject in node.subjects:
                result = self.__find_first_test(subject)
                if result:
                    return result

        return None







