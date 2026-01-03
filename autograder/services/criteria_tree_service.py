import logging
from typing import Optional

from autograder.models.abstract.template import Template
from autograder.models.config.criteria import CriteriaConfig
from autograder.models.criteria_tree import CriteriaTree
from autograder.parsers.criteria_tree import CriteriaTreeParser


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
        self.logger.info("Building criteria tree")

        parser = CriteriaTreeParser(template)
        tree = parser.parse_tree(criteria_config)

        self.logger.info("Criteria tree built successfully")
        return tree
