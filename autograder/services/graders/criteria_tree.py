import logging
from typing import Dict, Optional, Sequence, override
from autograder.models.criteria_tree import (
    CategoryNode,
    CriteriaTree,
    SubjectNode,
    TestNode,
)
from autograder.models.result_tree import (
    NodeType,
    ResultNode,
    ResultTree,
    TestResultNode,
)
from autograder.utils.processers.criteria_tree import CriteriaTreeProcesser


class CriteriaTreeGrader(CriteriaTreeProcesser):
    def __init__(self, submission_files: Dict) -> None:
        self.logger = logging.getLogger("GraderService")
        self.__submission_files = submission_files

    def __balance_nodes(self, nodes: Sequence[ResultNode], factor: float) -> None:
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

    def __process_holder(self, holder: CategoryNode | SubjectNode) -> ResultNode:
        result = ResultNode(
            name=holder.name,
            node_type=NodeType.CATEGORY
            if isinstance(holder, CategoryNode)
            else NodeType.SUBJECT,
            weight=holder.weight,
        )
        if holder.subjects and holder.tests:
            if not holder.subjects_weight:
                raise ValueError(f"missing 'subjects_weight' for {holder.name}")
            factor = holder.subjects_weight / 100.0
        else:
            factor = 1.0

        if holder.subjects:
            subject_results = [
                self.process_subject(inner_subject) for inner_subject in holder.subjects
            ]
            self.__balance_nodes(subject_results, factor)

        if holder.tests:
            test_results = [self.process_test(test) for test in holder.tests]
            self.__balance_nodes(test_results, factor)

        return result

    @override
    def process_subject(self, subject: SubjectNode) -> ResultNode:
        return self.__process_holder(subject)

    @override
    def process_test(self, test: TestNode) -> TestResultNode:
        test_result = TestResultNode(
            name=test.name,
            node_type=NodeType.TEST,
            weight=100.0,
            test_name=test.name,
            test_function=test.test_function,
            test_params=test.parameters,
            file_target=test.file_target,
        )
        test_result.execute(self.__submission_files)
        return test_result

    @override
    def process_category(self, category: CategoryNode) -> ResultNode:
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

    def grade(self, tree: CriteriaTree, submission_id: Optional[str]) -> ResultTree:
        self.logger.info(f"Grading from tree for submission: {submission_id}")

        root = ResultNode(name="root", node_type=NodeType.CATEGORY, weight=100.0)

        base_result = self.process_category(tree.base)
        root.children.append(base_result)

        if tree.bonus:
            bonus_result = self.process_category(tree.bonus)
            root.children.append(bonus_result)

        if tree.penalty:
            penalty_result = self.process_category(tree.penalty)
            root.children.append(penalty_result)

        result_tree = ResultTree(root, submission_id)

        # Handle AI executor batch if needed
        # Note: For tree-based grading, the template is embedded in test nodes
        first_test = self.__find_first_test(tree.base)
        if first_test and hasattr(first_test, "test_function"):
            test_func = first_test.test_function
            if hasattr(test_func, "executor") and test_func.executor:
                self.logger.info("Executing AI batch requests")
                test_func.executor.stop()

        return result_tree
