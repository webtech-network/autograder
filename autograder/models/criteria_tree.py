"""
Updated Criteria Tree models with embedded test functions.

These models represent the grading criteria structure with test functions
embedded during tree building (no more lazy loading or pre-execution).
"""

from typing import List, Optional, Any
from dataclasses import dataclass, field

from autograder.utils.formatters.criteria_tree import PreExecutedTreeFormatter
from autograder.utils.printers.criteria_tree import CriteriaTreePrinter


@dataclass
class TestNode:
    """
    Leaf node representing a single test execution configuration.

    Contains:
    - Test function reference (from template)
    - Parameters for execution
    - File target (if applicable)
    - Category and subject context
    """

    name: str
    test_name: str
    test_function: Any  # TestFunction instance from template
    parameters: List[Any] = field(default_factory=list)
    file_target: Optional[str] = None
    weight: float = 100.0

    def __repr__(self):
        params_str = f", params={self.parameters}" if self.parameters else ""
        file_str = f", file={self.file_target}" if self.file_target else ""
        return f"TestNode({self.test_name}{params_str}{file_str})"


@dataclass
class SubjectNode:
    """
    Branch node representing a subject/topic in the grading criteria.

    Can contain either:
    - Nested subjects (recursive structure)
    - Test nodes (leaf level)
    """

    name: str
    weight: float
    subjects: List["SubjectNode"] = field(default_factory=list)
    tests: List[TestNode] = field(default_factory=list)
    subjects_weight: Optional[float] = None

    def __repr__(self):
        if self.subjects:
            return f"SubjectNode({self.name}, weight={self.weight}, subjects={len(self.subjects)})"
        return (
            f"SubjectNode({self.name}, weight={self.weight}, tests={len(self.tests)})"
        )

    def get_all_tests(self) -> List[TestNode]:
        tests = [*self.tests]
        for subject in self.subjects:
            tests.extend(subject.get_all_tests())
        return tests


@dataclass
class CategoryNode:
    """
    Top-level category node (base, bonus, or penalty).

    Can contain either:
    - Subjects (organized hierarchy)
    - Tests (flat structure)
    """

    name: str
    weight: float
    subjects: List[SubjectNode] = field(default_factory=list)
    tests: List[TestNode] = field(default_factory=list)
    subjects_weight: Optional[float] = None

    def __repr__(self):
        if self.subjects:
            return f"CategoryNode({self.name}, weight={self.weight}, subjects={len(self.subjects)})"
        return (
            f"CategoryNode({self.name}, weight={self.weight}, tests={len(self.tests)})"
        )

    def add_subjects(self, subjects: List[SubjectNode]) -> None:
        self.subjects.extend(subjects)

    def get_all_tests(self) -> List[TestNode]:
        """Recursively collect all test nodes under this category."""
        tests = []

        if self.tests:
            tests.extend(self.tests)

        if self.subjects:
            for subject in self.subjects:
                tests.extend(subject.get_all_tests())

        return tests


@dataclass
class CriteriaTree:
    """
    Root of the criteria tree structure.

    Contains three main categories:
    - base: Required grading criteria
    - bonus: Optional bonus points
    - penalty: Optional penalty points
    """

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

    def print_tree(self):
        """Prints a visual representation of the entire criteria tree."""
        printer = CriteriaTreePrinter()
        printer.print_tree(self)

    def print_pre_executed_tree(self):
        """Prints a visual representation of the entire pre-executed criteria tree."""
        printer = CriteriaTreePrinter(PreExecutedTreeFormatter())
        printer.print_tree(self)
