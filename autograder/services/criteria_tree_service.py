"""Build the immutable criteria tree from an already-compiled definition.

Parameters arriving here are the canonical values of the definition snapshot.
Tree construction never validates or normalizes them again: evaluator
normalization happens exactly once, in ``compile_definition``.
"""
from typing import List, Mapping

from autograder.models.abstract.test_function import TestFunction
from autograder.models.config.criteria import CriteriaConfig
from autograder.models.config.subject import GroupConfig, SubjectConfig
from autograder.models.config.test import TestConfig
from autograder.models.criteria_tree import CategoryNode, CriteriaTree, SubjectNode, TestNode

#: The base category is the 0-100 score itself.
BASE_POINTS = 100.0


def build_criteria_tree(criteria: CriteriaConfig,
                        registry: Mapping[str, TestFunction]) -> CriteriaTree:
    """Embed each resolved evaluator with its canonical parameters."""
    def test(config: TestConfig) -> TestNode:
        return TestNode(
            name=config.name,
            test_function=registry[config.type],
            parameters=config.parameters,
            file_target=(config.file,) if config.file else None,
            weight=config.weight,
            criterion_id=config.id,
        )

    def subjects(configs: List[SubjectConfig]) -> tuple:
        # Subject weights are stored relative to their heaviest sibling.
        maximum = max((config.weight for config in configs), default=0)
        scaled_total = sum(config.weight / maximum for config in configs) if maximum > 0 else 0
        return tuple(
            SubjectNode(
                name=config.name,
                weight=(config.weight / maximum) / scaled_total * 100 if maximum > 0 else config.weight,
                subjects=subjects(config.subjects) if config.subjects else (),
                tests=tuple(test(item) for item in config.tests or ()),
                subjects_weight=config.subjects_weight,
            )
            for config in configs
        )

    def category(name: str, config: GroupConfig, points: float) -> CategoryNode:
        return CategoryNode(
            name=name,
            weight=points,
            subjects=subjects(config.subjects) if config.subjects else (),
            tests=tuple(test(item) for item in config.tests or ()),
            subjects_weight=config.subjects_weight,
        )

    return CriteriaTree(
        base=category("base", criteria.base, BASE_POINTS),
        bonus=category("bonus", criteria.bonus, criteria.bonus.max_points) if criteria.bonus else None,
        penalty=category("penalty", criteria.penalty, criteria.penalty.max_points) if criteria.penalty else None,
    )
