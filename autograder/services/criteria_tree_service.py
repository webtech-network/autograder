"""
Refactored CriteriaTreeService - builds criteria trees with embedded test functions.

This service is responsible for:
- Building CriteriaTree from validated CriteriaConfig
- Matching and embedding test functions from templates during tree building
- Validating that all tests exist in the template
- Balancing weights across sibling nodes
"""
import logging
from typing import List, Dict, Any, Optional

from autograder.models.criteria_tree import CriteriaTree, CategoryNode, SubjectNode, TestNode
from autograder.models.abstract.template import Template
from autograder.models.abstract.test_function import TestFunction
from autograder.models.dataclass.criteria_config import (
    CriteriaConfig,
    CategoryConfig,
    SubjectConfig,
    TestConfig
)


class CriteriaTreeService:
    """
    Service for building criteria trees from validated configuration.

    The tree building process now:
    1. Validates criteria config using Pydantic models
    2. Matches test functions from template during building
    3. Embeds test functions and parameters directly in TestNodes
    4. Balances weights across siblings

    This eliminates the need for pre-executed trees and improves error handling.
    """

    def __init__(self):
        self.logger = logging.getLogger("CriteriaTreeService")

    def build_tree(
        self,
        criteria_config: CriteriaConfig,
        template: Template
    ) -> CriteriaTree:
        """
        Build a complete criteria tree from validated configuration.

        Args:
            criteria_config: Validated criteria configuration
            template: Template containing test functions

        Returns:
            Complete CriteriaTree with embedded test functions

        Raises:
            ValueError: If test function not found in template
        """
        self.logger.info("Building criteria tree")

        tree = CriteriaTree()

        # Build base category (required)
        tree.base = self._build_category(
            "base",
            criteria_config.base,
            template
        )

        # Build bonus category (optional)
        if criteria_config.bonus:
            tree.bonus = self._build_category(
                "bonus",
                criteria_config.bonus,
                template
            )

        # Build penalty category (optional)
        if criteria_config.penalty:
            tree.penalty = self._build_category(
                "penalty",
                criteria_config.penalty,
                template
            )

        self.logger.info("Criteria tree built successfully")
        return tree

    def _build_category(
        self,
        category_name: str,
        category_config: CategoryConfig,
        template: Template
    ) -> CategoryNode:
        """Build a category node from configuration."""
        self.logger.debug(f"Building category: {category_name}")

        category = CategoryNode(name=category_name, weight=category_config.weight)

        # Category can have either subjects or tests
        if category_config.subjects:
            subjects = []
            # Subjects are now an array with subject_name field
            for subject_config in category_config.subjects:
                subject = self._build_subject(
                    subject_config.subject_name,
                    subject_config,
                    template,
                    category_name
                )
                subjects.append(subject)

            # Balance subject weights
            self._balance_weights(subjects)
            category.subjects = subjects

        elif category_config.tests:
            tests = self._build_tests(
                category_config.tests,
                template,
                category_name,
                category_name  # Use category as subject name
            )
            category.tests = tests

        return category

    def _build_subject(
        self,
        subject_name: str,
        subject_config: SubjectConfig,
        template: Template,
        category_name: str
    ) -> SubjectNode:
        """Recursively build a subject node from configuration."""
        self.logger.debug(f"Building subject: {subject_name}")

        subject = SubjectNode(name=subject_name, weight=subject_config.weight)

        # Subject can have either nested subjects or tests
        if subject_config.subjects:
            child_subjects = []
            # Subjects are now an array with subject_name field
            for child_config in subject_config.subjects:
                child = self._build_subject(
                    child_config.subject_name,
                    child_config,
                    template,
                    category_name
                )
                child_subjects.append(child)

            # Balance child weights
            self._balance_weights(child_subjects)
            subject.subjects = child_subjects

        elif subject_config.tests:
            tests = self._build_tests(
                subject_config.tests,
                template,
                category_name,
                subject_name
            )
            subject.tests = tests

        return subject

    def _build_tests(
        self,
        test_configs: List[TestConfig],
        template: Template,
        category_name: str,
        subject_name: str
    ) -> List[TestNode]:
        """
        Build test nodes from configuration with embedded test functions.

        New schema: Each test has named parameters directly (no 'calls' array).
        Creates one TestNode per test configuration.
        """
        test_nodes = []

        for test_index, test_config in enumerate(test_configs):
            # Find matching test function in template
            test_function = self._find_test_function(test_config.name, template)

            if not test_function:
                available_tests = "unknown"
                if hasattr(template, 'get_available_tests'):
                    try:
                        available_tests = ', '.join(template.get_available_tests())
                    except:
                        pass
                error_msg = (
                    f"Test function '{test_config.name}' not found in template. "
                    f"Available tests: {available_tests}"
                )
                self.logger.error(error_msg)
                raise ValueError(error_msg)

            # Convert named parameters to args list
            params = test_config.get_args_list() if test_config.parameters else []

            # Create single test node for this test configuration
            test_node = TestNode(
                name=f"{test_config.name}_{test_index}",
                test_name=test_config.name,
                test_function=test_function,
                parameters=params,
                file_target=test_config.file,
                category_name=category_name,
                subject_name=subject_name,
                weight=100.0  # Will be balanced with siblings
            )
            test_nodes.append(test_node)

            self.logger.debug(
                f"Created test node: {test_node.name} with params {params}"
            )

        # Balance weights across all test nodes at this level
        if test_nodes:
            self._balance_weights(test_nodes)

        return test_nodes

    def _find_test_function(
        self,
        test_name: str,
        template: Template
    ) -> Optional[TestFunction]:
        """
        Find a test function by name in the template.

        Args:
            test_name: Name of the test function to find
            template: Template to search in

        Returns:
            TestFunction if found, None otherwise
        """
        try:
            return template.get_test(test_name)
        except (AttributeError, KeyError):
            return None

    def _balance_weights(self, nodes: List) -> None:
        """
        Balance weights of sibling nodes to sum to 100.

        Args:
            nodes: List of sibling nodes (SubjectNode or TestNode)
        """
        if not nodes:
            return

        total_weight = sum(node.weight for node in nodes)

        if total_weight == 0:
            # If all weights are 0, distribute equally
            equal_weight = 100.0 / len(nodes)
            for node in nodes:
                node.weight = equal_weight
            self.logger.debug(f"Distributed equal weights: {equal_weight} each")
        elif total_weight != 100:
            # Scale weights to sum to 100
            scale_factor = 100.0 / total_weight
            for node in nodes:
                node.weight *= scale_factor
            self.logger.debug(f"Balanced weights with scale factor: {scale_factor}")


class CriteriaTreeBuilder:
    """
    Convenience builder class for creating criteria trees.

    Usage:
        builder = CriteriaTreeBuilder()
        tree = (builder
            .from_dict(criteria_dict)
            .with_template(template)
            .build())
    """

    def __init__(self):
        self._config: Optional[CriteriaConfig] = None
        self._template: Optional[Template] = None
        self._service = CriteriaTreeService()

    def from_dict(self, criteria_dict: dict) -> 'CriteriaTreeBuilder':
        """Load and validate criteria from dictionary."""
        self._config = CriteriaConfig.from_dict(criteria_dict)
        return self

    def from_json(self, criteria_json: str) -> 'CriteriaTreeBuilder':
        """Load and validate criteria from JSON string."""
        self._config = CriteriaConfig.from_json(criteria_json)
        return self

    def with_config(self, config: CriteriaConfig) -> 'CriteriaTreeBuilder':
        """Use an already validated CriteriaConfig."""
        self._config = config
        return self

    def with_template(self, template: Template) -> 'CriteriaTreeBuilder':
        """Set the template to use."""
        self._template = template
        return self

    def build(self) -> CriteriaTree:
        """Build the criteria tree."""
        if not self._config:
            raise ValueError("Criteria configuration not set. Use from_dict() or from_json()")
        if not self._template:
            raise ValueError("Template not set. Use with_template()")

        return self._service.build_tree(
            self._config,
            self._template
        )

