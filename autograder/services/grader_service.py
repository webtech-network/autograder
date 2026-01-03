"""
Enhanced GraderService - can build result trees from CriteriaTree or raw config.

This service handles two grading flows:
1. Single submission: Build result tree directly from criteria config (one-pass)
2. Multiple submissions: Build result tree from pre-built criteria tree (reusable)
"""
import logging
from typing import Dict, Any, Optional, List

from autograder.models.criteria_tree import CriteriaTree, CategoryNode, SubjectNode, TestNode
from autograder.models.result_tree import ResultTree, ResultNode, TestResultNode, NodeType
from autograder.models.abstract.template import Template
from autograder.models.dataclass.criteria_config import CriteriaConfig
from autograder.services.criteria_tree_service import CriteriaTreeService


class GraderService:
    """
    Service for executing grading and building result trees.

    Supports two modes:
    1. Direct grading: Build result tree from criteria config (single submission)
    2. Tree-based grading: Build result tree from criteria tree (multiple submissions)
    """

    def __init__(self):
        self.logger = logging.getLogger("GraderService")
        self._criteria_service = CriteriaTreeService()

    def grade_from_config(
        self,
        criteria_config: CriteriaConfig,
        template: Template,
        submission_files: Dict[str, Any],
        submission_id: Optional[str] = None
    ) -> ResultTree:
        """
        Grade a submission directly from criteria configuration (one-pass).

        This is optimized for single submissions - builds and executes in one traversal.

        Args:
            criteria_config: Validated criteria configuration
            template: Template with test functions
            submission_files: Student submission files
            submission_id: Optional identifier for the submission

        Returns:
            Complete ResultTree with all tests executed
        """
        self.logger.info(f"Grading from config for submission: {submission_id}")

        # Build root result node
        root = ResultNode(
            name="root",
            node_type=NodeType.CATEGORY,
            weight=100.0
        )

        # Build and execute base category (required)
        base_result = self._build_and_execute_category(
            "base",
            criteria_config.base,
            template,
            submission_files
        )
        root.children.append(base_result)

        # Build and execute bonus category (optional)
        if criteria_config.bonus:
            bonus_result = self._build_and_execute_category(
                "bonus",
                criteria_config.bonus,
                template,
                submission_files
            )
            root.children.append(bonus_result)

        # Build and execute penalty category (optional)
        if criteria_config.penalty:
            penalty_result = self._build_and_execute_category(
                "penalty",
                criteria_config.penalty,
                template,
                submission_files
            )
            root.children.append(penalty_result)

        # Create result tree and calculate scores
        result_tree = ResultTree(
            root=root,
            submission_id=submission_id,
            template_name=template.name if hasattr(template, 'name') else None
        )

        # Handle AI executor batch if needed
        if hasattr(template, 'execution_helper') and template.execution_helper:
            self.logger.info("Executing AI batch requests")
            template.execution_helper.stop()

        # Calculate final scores
        final_score = result_tree.calculate_final_score()
        self.logger.info(f"Grading complete. Final score: {final_score}")

        return result_tree

    def grade_from_tree(
        self,
        criteria_tree: CriteriaTree,
        submission_files: Dict[str, Any],
        submission_id: Optional[str] = None
    ) -> ResultTree:
        """
        Grade a submission using a pre-built criteria tree.

        This is optimized for multiple submissions - reuses the same criteria tree.

        Args:
            criteria_tree: Pre-built criteria tree with test functions
            submission_files: Student submission files
            submission_id: Optional identifier for the submission

        Returns:
            Complete ResultTree with all tests executed
        """
        self.logger.info(f"Grading from tree for submission: {submission_id}")

        # Build root result node
        root = ResultNode(
            name="root",
            node_type=NodeType.CATEGORY,
            weight=100.0
        )

        # Execute base category
        if criteria_tree.base:
            base_result = self._execute_category(
                criteria_tree.base,
                submission_files
            )
            root.children.append(base_result)

        # Execute bonus category
        if criteria_tree.bonus:
            bonus_result = self._execute_category(
                criteria_tree.bonus,
                submission_files
            )
            root.children.append(bonus_result)

        # Execute penalty category
        if criteria_tree.penalty:
            penalty_result = self._execute_category(
                criteria_tree.penalty,
                submission_files
            )
            root.children.append(penalty_result)

        # Create result tree
        result_tree = ResultTree(
            root=root,
            submission_id=submission_id
        )

        # Handle AI executor batch if needed
        # Note: For tree-based grading, the template is embedded in test nodes
        first_test = self._find_first_test(criteria_tree.base)
        if first_test and hasattr(first_test, 'test_function'):
            test_func = first_test.test_function
            if hasattr(test_func, 'executor') and test_func.executor:
                self.logger.info("Executing AI batch requests")
                test_func.executor.stop()

        # Calculate final scores
        final_score = result_tree.calculate_final_score()
        self.logger.info(f"Grading complete. Final score: {final_score}")

        return result_tree

    def _build_and_execute_category(
        self,
        category_name: str,
        category_config,
        template: Template,
        submission_files: Dict[str, Any]
    ) -> ResultNode:
        """Build and execute a category in one pass."""
        category_result = ResultNode(
            name=category_name,
            node_type=NodeType.CATEGORY,
            weight=category_config.weight
        )

        # Category has either subjects or tests
        if category_config.subjects:
            # Subjects are now an array with subject_name field
            for subject_config in category_config.subjects:
                subject_result = self._build_and_execute_subject(
                    subject_config.subject_name,
                    subject_config,
                    template,
                    submission_files,
                    category_name
                )
                category_result.children.append(subject_result)

            # Balance weights
            self._balance_weights(category_result.children)

        elif category_config.tests:
            test_results = self._build_and_execute_tests(
                category_config.tests,
                template,
                submission_files,
                category_name,
                category_name
            )
            category_result.children.extend(test_results)

        return category_result

    def _build_and_execute_subject(
        self,
        subject_name: str,
        subject_config,
        template: Template,
        submission_files: Dict[str, Any],
        category_name: str
    ) -> ResultNode:
        """Recursively build and execute a subject in one pass."""
        subject_result = ResultNode(
            name=subject_name,
            node_type=NodeType.SUBJECT,
            weight=subject_config.weight
        )

        # Subject has either nested subjects or tests
        if subject_config.subjects:
            # Subjects are now an array with subject_name field
            for child_config in subject_config.subjects:
                child_result = self._build_and_execute_subject(
                    child_config.subject_name,
                    child_config,
                    template,
                    submission_files,
                    category_name
                )
                subject_result.children.append(child_result)

            # Balance weights
            self._balance_weights(subject_result.children)

        elif subject_config.tests:
            test_results = self._build_and_execute_tests(
                subject_config.tests,
                template,
                submission_files,
                category_name,
                subject_name
            )
            subject_result.children.extend(test_results)

        return subject_result

    def _build_and_execute_tests(
        self,
        test_configs: List,
        template: Template,
        submission_files: Dict[str, Any],
        category_name: str,
        subject_name: str
    ) -> List[TestResultNode]:
        """Build and execute test nodes."""
        test_results = []

        for test_index, test_config in enumerate(test_configs):
            # Find test function
            test_function = template.get_test(test_config.name)

            if not test_function:
                raise ValueError(
                    f"Test '{test_config.name}' not found in template"
                )

            # Convert named parameters to args list
            params = test_config.get_args_list() if test_config.parameters else []

            # Create and execute test node
            test_node = TestResultNode(
                name=f"{test_config.name}_{test_index}",
                node_type=NodeType.TEST,
                weight=100.0,  # Will be balanced
                test_name=test_config.name,
                test_function=test_function,
                test_params=params,
                file_target=test_config.file
            )

            # Execute test
            test_node.execute(submission_files)
            test_results.append(test_node)

        # Balance weights
        if test_results:
            self._balance_weights(test_results)

        return test_results

    def _execute_category(
        self,
        category_node: CategoryNode,
        submission_files: Dict[str, Any]
    ) -> ResultNode:
        """Execute a category from criteria tree."""
        category_result = ResultNode(
            name=category_node.name,
            node_type=NodeType.CATEGORY,
            weight=category_node.weight
        )

        # Execute subjects
        if hasattr(category_node, 'subjects') and category_node.subjects:
            for subject in category_node.subjects:
                subject_result = self._execute_subject(subject, submission_files)
                category_result.children.append(subject_result)

        # Execute tests
        if hasattr(category_node, 'tests') and category_node.tests:
            for test in category_node.tests:
                test_result = self._execute_test(test, submission_files)
                category_result.children.append(test_result)

        return category_result

    def _execute_subject(
        self,
        subject_node: SubjectNode,
        submission_files: Dict[str, Any]
    ) -> ResultNode:
        """Execute a subject from criteria tree."""
        subject_result = ResultNode(
            name=subject_node.name,
            node_type=NodeType.SUBJECT,
            weight=subject_node.weight
        )

        # Execute nested subjects
        if hasattr(subject_node, 'subjects') and subject_node.subjects:
            for child in subject_node.subjects:
                child_result = self._execute_subject(child, submission_files)
                subject_result.children.append(child_result)

        # Execute tests
        if hasattr(subject_node, 'tests') and subject_node.tests:
            for test in subject_node.tests:
                test_result = self._execute_test(test, submission_files)
                subject_result.children.append(test_result)

        return subject_result

    def _execute_test(
        self,
        test_node: TestNode,
        submission_files: Dict[str, Any]
    ) -> TestResultNode:
        """Execute a single test from criteria tree."""
        result_node = TestResultNode(
            name=test_node.name,
            node_type=NodeType.TEST,
            weight=test_node.weight,
            test_name=test_node.test_name,
            test_function=test_node.test_function,
            test_params=test_node.parameters,
            file_target=test_node.file_target
        )

        # Execute the test
        result_node.execute(submission_files)

        return result_node

    def _balance_weights(self, nodes: List[ResultNode]) -> None:
        """Balance weights of sibling nodes to sum to 100."""
        if not nodes:
            return

        total_weight = sum(node.weight for node in nodes)

        if total_weight == 0:
            equal_weight = 100.0 / len(nodes)
            for node in nodes:
                node.weight = equal_weight
        elif total_weight != 100:
            scale_factor = 100.0 / total_weight
            for node in nodes:
                node.weight *= scale_factor

    def _find_first_test(self, node) -> Optional[TestNode]:
        """Find the first test node in the tree."""
        if isinstance(node, TestNode):
            return node

        if hasattr(node, 'tests') and node.tests:
            return node.tests[0]

        if hasattr(node, 'subjects') and node.subjects:
            for subject in node.subjects:
                result = self._find_first_test(subject)
                if result:
                    return result

        return None

