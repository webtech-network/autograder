import logging
from typing import Optional

from autograder.models.abstract.template import Template
from autograder.models.config.criteria import CriteriaConfig
from autograder.models.criteria_tree import CriteriaTree


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

        self.logger.info("Criteria tree built successfully")
        return tree


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

    def from_dict(self, criteria_dict: dict) -> "CriteriaTreeBuilder":
        """Load and validate criteria from dictionary."""
        self._config = CriteriaConfig.from_dict(criteria_dict)
        return self

    def from_json(self, criteria_json: str) -> "CriteriaTreeBuilder":
        """Load and validate criteria from JSON string."""
        self._config = CriteriaConfig.from_json(criteria_json)
        return self

    def with_config(self, config: CriteriaConfig) -> "CriteriaTreeBuilder":
        """Use an already validated CriteriaConfig."""
        self._config = config
        return self

    def with_template(self, template: Template) -> "CriteriaTreeBuilder":
        """Set the template to use."""
        self._template = template
        return self

    def build(self) -> CriteriaTree:
        """Build the criteria tree."""
        if not self._config:
            raise ValueError(
                "Criteria configuration not set. Use from_dict() or from_json()"
            )
        if not self._template:
            raise ValueError("Template not set. Use with_template()")

        return self._service.build_tree(self._config, self._template)
