"""
Result Tree Models

The Result Tree is the stateful representation of a grading session, produced by executing
a Criteria Tree on a student submission.

Structure Overview:
- ResultTree: Root container holding the entire result hierarchy
- CategoryResultNode: Top-level results (base, bonus, penalty)
- SubjectResultNode: Mid-level topic/subject results
- TestResultNode: Leaf-level individual test execution results

Key Differences from Criteria Tree:
- Criteria Tree is stateless (assignment definition)
- Result Tree is stateful (execution results for a specific submission)
- Result Tree contains actual scores, reports, and execution metadata
- Result Tree mirrors Criteria Tree structure but with computed results

Each node calculates its score based on its children's weighted scores.
The final score flows up from test results through subjects and categories to the root.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
import copy

from autograder.models.criteria_tree import TestNode


@dataclass
class TestResultNode:
    """
    Leaf node containing the outcome of a single test execution.

    This represents the result of running a specific test function from the template
    on the student's submission. Contains the score, report, and execution metadata.

    Attributes:
        name: Name of the test
        test_node: Reference to the original TestNode from the criteria tree
        score: Test score (0-100)
        report: Human-readable feedback/report from the test execution
        weight: Weight of this test in its parent subject
        parameters: Parameters used for test execution
        metadata: Additional execution metadata
    """

    name: str
    test_node: TestNode
    score: float
    report: str
    weight: float = 100.0
    parameters: Optional[Dict[str, Any]] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def calculate_score(self) -> float:
        """Test nodes return their own score (leaf nodes)."""
        return self.score

    def to_dict(self) -> dict:
        """Convert test result to dictionary representation."""
        return {
            "name": self.name,
            "type": "test",
            "score": round(self.score, 2),
            "weight": self.weight,
            "report": self.report,
            "file_target": self.test_node.file_target,
            "parameters": self.parameters,
            "metadata": self.metadata,
        }


@dataclass
class SubjectResultNode:
    """
    Branch node representing results for a subject/topic.

    Contains either nested subjects or test results, with a calculated score
    based on the weighted average of its children.

    Attributes:
        name: Name of the subject
        weight: Weight of this subject in its parent category/subject
        score: Calculated weighted average score of children
        subjects: Nested subject results (if any)
        tests: Test results directly under this subject (if any)
        metadata: Additional metadata
    """

    name: str
    weight: float
    subjects_weight: Optional[float]
    score: float = 0.0
    subjects: List["SubjectResultNode"] = field(default_factory=list)
    tests: List[TestResultNode] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def calculate_score(self) -> float:
        """
        Calculate score as weighted average of children (subjects and tests).

        Returns:
            Calculated score (0-100)
        """
        # Calculate children scores first
        for subject in self.subjects:
            subject.calculate_score()
        for test in self.tests:
            test.calculate_score()

        # Combine all children
        all_children = list(self.subjects) + list(self.tests)

        if not all_children:
            return 0.0

        # Calculate weighted average
        total_weight = sum(child.weight for child in all_children)
        if total_weight == 0:
            return 0.0

        weighted_sum = sum(child.score * child.weight for child in all_children)
        self.score = weighted_sum / total_weight

        return self.score

    def to_dict(self) -> dict:
        """Convert subject result to dictionary representation."""
        return {
            "name": self.name,
            "type": "subject",
            "weight": self.weight,
            "score": round(self.score, 2),
            "subjects": [subject.to_dict() for subject in self.subjects],
            "tests": [test.to_dict() for test in self.tests],
            "metadata": self.metadata,
        }

    def get_all_test_results(self) -> List[TestResultNode]:
        """Recursively collect all test results under this subject."""
        results = list(self.tests)
        for subject in self.subjects:
            results.extend(subject.get_all_test_results())
        return results


@dataclass
class CategoryResultNode:
    """
    Top-level category result node (base, bonus, or penalty).

    Represents the aggregated results for a major grading category.
    Can contain subjects (organized hierarchy) or tests (flat structure).

    Attributes:
        name: Name of the category (e.g., "base", "bonus", "penalty")
        weight: Weight of this category (typically 100 for base, varies for bonus/penalty)
        score: Calculated weighted average score of children
        subjects: Subject results under this category (if any)
        tests: Test results directly under this category (if any)
        metadata: Additional metadata
    """

    name: str
    weight: float
    subjects_weight: Optional[float] = None
    score: float = 0.0
    subjects: List[SubjectResultNode] = field(default_factory=list)
    tests: List[TestResultNode] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def calculate_score(self) -> float:
        """
        Calculate score as weighted average of children (subjects and tests).

        Returns:
            Calculated score (0-100)
        """
        # Calculate children scores first
        for subject in self.subjects:
            subject.calculate_score()
        for test in self.tests:
            test.calculate_score()

        # Combine all children
        all_children = list(self.subjects) + list(self.tests)

        if not all_children:
            return 0.0

        # Calculate weighted average
        total_weight = sum(child.weight for child in all_children)
        if total_weight == 0:
            return 0.0

        weighted_sum = sum(child.score * child.weight for child in all_children)
        self.score = weighted_sum / total_weight

        return self.score

    def to_dict(self) -> dict:
        """Convert category result to dictionary representation."""
        return {
            "name": self.name,
            "type": "category",
            "weight": self.weight,
            "score": round(self.score, 2),
            "subjects": [subject.to_dict() for subject in self.subjects],
            "tests": [test.to_dict() for test in self.tests],
            "metadata": self.metadata,
        }

    def get_all_test_results(self) -> List[TestResultNode]:
        """Recursively collect all test results under this category."""
        results = list(self.tests)
        for subject in self.subjects:
            results.extend(subject.get_all_test_results())
        return results


@dataclass
class RootResultNode:
    """
    Root node of the result tree, containing category results.

    Special scoring logic for BASE/BONUS/PENALTY categories:
    - Base: Standard 0-100 score
    - Bonus: Adds points (bonus_score * bonus_weight / 100)
    - Penalty: Subtracts points (penalty_score * penalty_weight / 100)
    - Final score = base + bonus - penalty (capped at 0-100)

    Attributes:
        name: Always "root"
        score: Final calculated score
        base: Base category result (required)
        bonus: Bonus category result (optional)
        penalty: Penalty category result (optional)
        metadata: Additional metadata
    """

    base: CategoryResultNode
    name: str = "root"
    score: float = 0.0
    bonus: Optional[CategoryResultNode] = None
    penalty: Optional[CategoryResultNode] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def calculate_score(self) -> float:
        """
        Calculate final score using additive BASE/BONUS/PENALTY logic.

        Returns:
            Final score (0-100)
        """
        # Calculate category scores first
        base_score = 0.0
        if self.base:
            base_score = self.base.calculate_score()

        bonus_points = 0.0
        if self.bonus:
            bonus_score = self.bonus.calculate_score()
            # Bonus adds: (bonus_score / 100) * bonus_weight
            bonus_points = (bonus_score / 100.0) * self.bonus.weight

        penalty_points = 0.0
        if self.penalty:
            penalty_score = self.penalty.calculate_score()
            # Penalty subtracts: (penalty_score / 100) * penalty_weight
            penalty_points = (penalty_score / 100.0) * self.penalty.weight

        # Final score = base + bonus - penalty (capped at 0-100)
        self.score = max(0.0, min(100.0, base_score + bonus_points - penalty_points))

        return self.score

    def to_dict(self) -> dict:
        """Convert root node to dictionary representation."""
        result = {
            "name": self.name,
            "type": "root",
            "score": round(self.score, 2),
            "metadata": self.metadata,
            "base": self.base.to_dict(),
        }

        if self.bonus:
            result["bonus"] = self.bonus.to_dict()

        if self.penalty:
            result["penalty"] = self.penalty.to_dict()

        return result

    def get_all_categories(self) -> List[CategoryResultNode]:
        """Get all category nodes."""
        categories = []
        if self.base:
            categories.append(self.base)
        if self.bonus:
            categories.append(self.bonus)
        if self.penalty:
            categories.append(self.penalty)
        return categories

    def get_all_test_results(self) -> List[TestResultNode]:
        """Recursively collect all test results from all categories."""
        results = []
        for category in self.get_all_categories():
            results.extend(category.get_all_test_results())
        return results


@dataclass
class ResultTree:
    """
    Complete result tree for a grading session.

    This is the stateful product of executing a Criteria Tree on a student submission.
    It mirrors the structure of the Criteria Tree but contains actual execution results,
    scores, and feedback for each test.

    The tree flows from:
    Root -> Categories (base/bonus/penalty) -> Subjects -> Tests

    Scores are calculated bottom-up: test scores aggregate into subject scores,
    which aggregate into category scores, which produce the final root score.

    Attributes:
        root: Root node containing all category results
        template_name: Name of the template used for grading (optional)
        metadata: Additional grading session metadata
    """

    root: RootResultNode
    template_name: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def calculate_final_score(self) -> float:
        """
        Calculate and return the final score by traversing the tree.

        Returns:
            Final score (0-100)
        """
        return self.root.calculate_score()

    def get_all_test_results(self) -> List[TestResultNode]:
        """Get all test result nodes from the entire tree."""
        return self.root.get_all_test_results()

    def get_failed_tests(self) -> List[TestResultNode]:
        """Get all test nodes with score below 100."""
        return [test for test in self.get_all_test_results() if test.score < 100]

    def get_passed_tests(self) -> List[TestResultNode]:
        """Get all test nodes with score of 100."""
        return [test for test in self.get_all_test_results() if test.score >= 100]

    def to_dict(self) -> dict:
        """Convert entire result tree to dictionary."""
        all_tests = self.get_all_test_results()
        passed_tests = self.get_passed_tests()
        failed_tests = self.get_failed_tests()

        return {
            "template_name": self.template_name,
            "final_score": round(self.root.score, 2),
            "tree": self.root.to_dict(),
            "metadata": self.metadata,
            "summary": {
                "total_tests": len(all_tests),
                "passed_tests": len(passed_tests),
                "failed_tests": len(failed_tests),
            },
        }
