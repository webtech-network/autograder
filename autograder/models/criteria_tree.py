"""
Updated Criteria Tree models with embedded test functions.

These models represent the grading criteria structure with test functions
embedded during tree building (no more lazy loading or pre-execution).
"""
from typing import List, Optional, Any
from dataclasses import dataclass, field


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
    category_name: str = ""
    subject_name: str = ""
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
    subjects: List['SubjectNode'] = field(default_factory=list)
    tests: List[TestNode] = field(default_factory=list)

    def __repr__(self):
        if self.subjects:
            return f"SubjectNode({self.name}, weight={self.weight}, subjects={len(self.subjects)})"
        return f"SubjectNode({self.name}, weight={self.weight}, tests={len(self.tests)})"

    def get_all_tests(self) -> List[TestNode]:
        """Recursively collect all test nodes under this subject."""
        tests = []

        if self.tests:
            tests.extend(self.tests)

        if self.subjects:
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

    def __repr__(self):
        if self.subjects:
            return f"CategoryNode({self.name}, weight={self.weight}, subjects={len(self.subjects)})"
        return f"CategoryNode({self.name}, weight={self.weight}, tests={len(self.tests)})"

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
    base: Optional[CategoryNode] = None
    bonus: Optional[CategoryNode] = None
    penalty: Optional[CategoryNode] = None

    def __repr__(self):
        categories = []
        if self.base:
            categories.append("base")
        if self.bonus:
            categories.append("bonus")
        if self.penalty:
            categories.append("penalty")
        return f"CriteriaTree(categories={categories})"

    def get_all_tests(self) -> List[TestNode]:
        """Get all test nodes from the entire tree."""
        tests = []

        if self.base:
            tests.extend(self.base.get_all_tests())
        if self.bonus:
            tests.extend(self.bonus.get_all_tests())
        if self.penalty:
            tests.extend(self.penalty.get_all_tests())

        return tests

    def print_tree(self):
        """Print a visual representation of the criteria tree."""
        print("🌲 Criteria Tree")

        if self.base:
            self._print_category(self.base, "  ")
        if self.bonus:
            self._print_category(self.bonus, "  ")
        if self.penalty:
            self._print_category(self.penalty, "  ")

    def _print_category(self, category: CategoryNode, prefix: str):
        """Print a category and its contents."""
        print(f"{prefix}📁 {category.name.upper()} (weight: {category.weight})")

        if category.subjects:
            for subject in category.subjects:
                self._print_subject(subject, prefix + "    ")

        if category.tests:
            for test in category.tests:
                params = f"({test.parameters})" if test.parameters else "()"
                file_info = f" [file: {test.file_target}]" if test.file_target else ""
                print(f"{prefix}    🧪 {test.test_name}{params}{file_info}")

    def _print_subject(self, subject: SubjectNode, prefix: str):
        """Recursively print a subject and its contents."""
        print(f"{prefix}📘 {subject.name} (weight: {subject.weight})")

        if subject.subjects:
            for child in subject.subjects:
                self._print_subject(child, prefix + "    ")

        if subject.tests:
            for test in subject.tests:
                params = f"({test.parameters})" if test.parameters else "()"
                file_info = f" [file: {test.file_target}]" if test.file_target else ""
                print(f"{prefix}    🧪 {test.test_name}{params}{file_info}")

