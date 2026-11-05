"""Immutable compiled criteria tree.

Nodes are built once by ``compile_definition`` from canonical parameters and
never change afterwards. Parameters are deeply frozen; use
``autograder.models.frozen.thaw`` to obtain an isolated mutable copy.
"""

from dataclasses import dataclass, field
from typing import Any, FrozenSet, List, Mapping, Optional, Tuple

from autograder.models.abstract.test_function import TestFunction
from autograder.models.frozen import freeze


@dataclass(frozen=True)
class TestNode:
    """One criterion: its trusted evaluator, canonical parameters and targets."""

    name: str
    test_function: TestFunction
    parameters: Mapping[str, Any] = field(default_factory=dict)
    file_target: Optional[Tuple[str, ...]] = None
    weight: float = 100.0
    criterion_id: str = ""

    def __post_init__(self):
        object.__setattr__(self, "parameters", freeze(self.parameters))
        if self.file_target is not None:
            object.__setattr__(self, "file_target", tuple(self.file_target))

    @property
    def capabilities(self) -> FrozenSet[str]:
        """Host capabilities, exactly as the evaluator declares them (no other source)."""
        return frozenset(self.test_function.required_capabilities)

    def __repr__(self):
        params_str = f", params={dict(self.parameters)}" if self.parameters else ""
        file_str = f", file={list(self.file_target)}" if self.file_target else ""
        return f"TestNode({self.name}{params_str}{file_str})"


def _all_tests(holder) -> List[TestNode]:
    """Nested subjects precede a holder's direct tests: the execution order."""
    tests = []
    for subject in holder.subjects:
        tests.extend(_all_tests(subject))
    tests.extend(holder.tests)
    return tests


@dataclass(frozen=True)
class SubjectNode:
    """A weighted group of nested subjects and/or tests."""

    name: str
    weight: float
    subjects: Tuple["SubjectNode", ...] = ()
    tests: Tuple[TestNode, ...] = ()
    subjects_weight: Optional[float] = None

    def __post_init__(self):
        object.__setattr__(self, "subjects", tuple(self.subjects))
        object.__setattr__(self, "tests", tuple(self.tests))

    def __repr__(self):
        if self.subjects:
            return f"SubjectNode({self.name}, weight={self.weight}, subjects={len(self.subjects)})"
        return f"SubjectNode({self.name}, weight={self.weight}, tests={len(self.tests)})"

    def get_all_tests(self) -> List[TestNode]:
        """Recursively collect all test nodes under this subject."""
        return _all_tests(self)


@dataclass(frozen=True)
class CategoryNode:
    """Top-level category node (base, bonus, or penalty)."""

    name: str
    weight: float
    subjects: Tuple[SubjectNode, ...] = ()
    tests: Tuple[TestNode, ...] = ()
    subjects_weight: Optional[float] = None

    def __post_init__(self):
        object.__setattr__(self, "subjects", tuple(self.subjects))
        object.__setattr__(self, "tests", tuple(self.tests))

    def __repr__(self):
        if self.subjects:
            return f"CategoryNode({self.name}, weight={self.weight}, subjects={len(self.subjects)})"
        return f"CategoryNode({self.name}, weight={self.weight}, tests={len(self.tests)})"

    def get_all_tests(self) -> List[TestNode]:
        """Recursively collect all test nodes under this category."""
        return _all_tests(self)


@dataclass(frozen=True)
class CriteriaTree:
    """Root of the compiled criteria: base plus optional bonus and penalty."""

    base: CategoryNode
    bonus: Optional[CategoryNode] = None
    penalty: Optional[CategoryNode] = None

    def __repr__(self):
        categories = ["base"]
        if self.bonus:
            categories.append("bonus")
        if self.penalty:
            categories.append("penalty")
        return f"CriteriaTree(categories={categories})"

    def categories(self) -> List[CategoryNode]:
        """Present categories in base, bonus, penalty order."""
        return [category for category in (self.base, self.bonus, self.penalty) if category is not None]

    def get_all_tests(self) -> List[TestNode]:
        """Every criterion in deterministic definition order."""
        return [test for category in self.categories() for test in category.get_all_tests()]
