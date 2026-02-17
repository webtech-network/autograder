import logging
from typing import List, Optional

from autograder.models.abstract.template import Template
from autograder.models.abstract.test_function import TestFunction
from autograder.models.config.category import CategoryConfig
from autograder.models.config.criteria import CriteriaConfig
from autograder.models.config.subject import SubjectConfig
from autograder.models.config.test import TestConfig
from autograder.models.criteria_tree import CriteriaTree, SubjectNode, TestNode, CategoryNode


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
        self.__template = None

    def build_tree(
        self, criteria_config: CriteriaConfig, template: Template
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

        self.__template = template

        base_category = self.__parse_category("base", criteria_config.base)
        tree = CriteriaTree(base_category)

        if criteria_config.bonus:
            tree.bonus = self.__parse_category("bonus", criteria_config.bonus)

        if criteria_config.penalty:
            tree.penalty = self.__parse_category("penalty", criteria_config.penalty)

        return tree

    def __parse_subjects(self, configs: List[SubjectConfig]) -> List[SubjectNode]:
        subjects = [self.__parse_subject(config) for config in configs]
        self.__balance_subject_weights(subjects)
        return subjects

    def __parse_subject(self, config: SubjectConfig) -> SubjectNode:
        subject = SubjectNode(config.subject_name, config.weight)

        subject.subjects_weight = config.subjects_weight

        if config.subjects:
            subject.subjects = self.__parse_subjects(config.subjects)

        if config.tests:
            subject.tests = self.__parse_tests(config.tests)

        return subject

    def __balance_subject_weights(self, subjects: List[SubjectNode]) -> None:
        total_weight = sum(s.weight for s in subjects)
        if total_weight > 0 and total_weight != 100:
            scaling_factor = 100 / total_weight
            for subject in subjects:
                subject.weight = subject.weight * scaling_factor

    def __parse_tests(self, test_configs: List[TestConfig]) -> List[TestNode]:
        return [self.__parse_test(test_item) for test_item in test_configs]

    def __find_test_function(self, name: str) -> Optional[TestFunction]:
        try:
            return self.__template.get_test(name)
        except (AttributeError, KeyError):
            return None

    def __parse_test(self, config: TestConfig) -> TestNode:
        test_function = self.__find_test_function(config.name)
        if not test_function:
            raise ValueError(f"Couldn't find test {config.name}")

        test = TestNode(
            config.name,
            test_function,
            config.get_kwargs_dict() or dict(),
            config.file,
        )

        return test

    def __parse_category(self, category_name, config: CategoryConfig) -> CategoryNode:
        category = CategoryNode(category_name, config.weight)

        category.subjects_weight = config.subjects_weight

        if config.subjects:
            category.add_subjects(self.__parse_subjects(config.subjects))

        if config.tests:
            category.tests = self.__parse_tests(config.tests)

        return category
