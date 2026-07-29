"""
Unit tests for ResultTree.iter_test_results() and ResultTree.to_score_vector().

Tests cover:
1. Simple tree with base category only
2. Full tree with base, bonus, and penalty categories
3. Deeply nested subjects (3+ levels)
4. Tests directly under categories (flat structure, no subjects)
5. Mixed structure — subjects and direct tests on the same category
6. Empty tree with no tests
7. Path format correctness
8. Score vector output matches expected dict
9. Score vector is empty for empty trees
"""

from unittest.mock import MagicMock

from autograder.models.criteria_tree import TestNode
from autograder.models.result_tree import (
    CategoryResultNode,
    ResultTree,
    RootResultNode,
    SubjectResultNode,
    TestResultNode,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_test_node(name: str) -> TestNode:
    """Create a minimal TestNode stub for use in TestResultNode."""
    node = MagicMock(spec=TestNode)
    node.name = name
    node.file_target = None
    return node


def _make_test_result(name: str, score: float, weight: float = 100.0) -> TestResultNode:
    """Create a TestResultNode with the given name and score."""
    return TestResultNode(
        name=name,
        test_node=_make_test_node(name),
        score=score,
        report=f"Report for {name}",
        weight=weight,
    )


def _make_subject(
    name: str,
    weight: float = 100.0,
    subjects: list = None,
    tests: list = None,
    subjects_weight: float = None,
) -> SubjectResultNode:
    """Create a SubjectResultNode."""
    return SubjectResultNode(
        name=name,
        weight=weight,
        subjects_weight=subjects_weight,
        subjects=subjects or [],
        tests=tests or [],
    )


def _make_category(
    name: str,
    weight: float = 100.0,
    subjects: list = None,
    tests: list = None,
    subjects_weight: float = None,
) -> CategoryResultNode:
    """Create a CategoryResultNode."""
    return CategoryResultNode(
        name=name,
        weight=weight,
        subjects_weight=subjects_weight,
        subjects=subjects or [],
        tests=tests or [],
    )


def _make_tree(
    base: CategoryResultNode,
    bonus: CategoryResultNode = None,
    penalty: CategoryResultNode = None,
) -> ResultTree:
    """Create a ResultTree with the given categories."""
    root = RootResultNode(base=base, bonus=bonus, penalty=penalty)
    return ResultTree(root=root)


# ---------------------------------------------------------------------------
# iter_test_results() tests
# ---------------------------------------------------------------------------

class TestIterTestResults:
    """Tests for ResultTree.iter_test_results()."""

    def test_simple_base_only(self):
        """Base category with one subject and two tests."""
        tree = _make_tree(
            base=_make_category("base", subjects=[
                _make_subject("code_quality", tests=[
                    _make_test_result("cyclomatic_complexity", 72.0),
                    _make_test_result("line_length", 95.0),
                ]),
            ]),
        )

        results = list(tree.iter_test_results())

        assert len(results) == 2
        assert results[0][0] == "base/code_quality/cyclomatic_complexity"
        assert results[0][1].score == 72.0
        assert results[1][0] == "base/code_quality/line_length"
        assert results[1][1].score == 95.0

    def test_all_three_categories(self):
        """Tree with base, bonus, and penalty categories."""
        tree = _make_tree(
            base=_make_category("base", subjects=[
                _make_subject("tests", tests=[
                    _make_test_result("test_basic", 80.0),
                ]),
            ]),
            bonus=_make_category("bonus", weight=10, subjects=[
                _make_subject("extras", tests=[
                    _make_test_result("extra_credit", 100.0),
                ]),
            ]),
            penalty=_make_category("penalty", weight=20, subjects=[
                _make_subject("hygiene", tests=[
                    _make_test_result("code_duplication", 45.0),
                ]),
            ]),
        )

        results = list(tree.iter_test_results())
        paths = [path for path, _ in results]

        assert len(results) == 3
        assert "base/tests/test_basic" in paths
        assert "bonus/extras/extra_credit" in paths
        assert "penalty/hygiene/code_duplication" in paths

    def test_deeply_nested_subjects(self):
        """Three levels of subject nesting: category/s1/s2/s3/test."""
        tree = _make_tree(
            base=_make_category("base", subjects=[
                _make_subject("level1", subjects=[
                    _make_subject("level2", subjects=[
                        _make_subject("level3", tests=[
                            _make_test_result("deep_test", 55.0),
                        ]),
                    ]),
                ]),
            ]),
        )

        results = list(tree.iter_test_results())

        assert len(results) == 1
        assert results[0][0] == "base/level1/level2/level3/deep_test"
        assert results[0][1].score == 55.0

    def test_tests_directly_under_category(self):
        """Tests attached directly to a category (no subjects)."""
        tree = _make_tree(
            base=_make_category("base", tests=[
                _make_test_result("flat_test_a", 90.0),
                _make_test_result("flat_test_b", 60.0),
            ]),
        )

        results = list(tree.iter_test_results())
        paths = [path for path, _ in results]

        assert len(results) == 2
        assert paths == ["base/flat_test_a", "base/flat_test_b"]

    def test_mixed_subjects_and_direct_tests_on_category(self):
        """Category has both subjects and direct tests — both should appear."""
        tree = _make_tree(
            base=_make_category("base",
                subjects=[
                    _make_subject("group_a", tests=[
                        _make_test_result("grouped_test", 70.0),
                    ]),
                ],
                tests=[
                    _make_test_result("ungrouped_test", 85.0),
                ],
            ),
        )

        results = list(tree.iter_test_results())
        paths = [path for path, _ in results]

        assert len(results) == 2
        # Subjects come before direct tests (iteration order)
        assert paths[0] == "base/group_a/grouped_test"
        assert paths[1] == "base/ungrouped_test"

    def test_mixed_subjects_and_tests_on_subject(self):
        """Subject has both nested subjects and direct tests."""
        tree = _make_tree(
            base=_make_category("base", subjects=[
                _make_subject("parent",
                    subjects=[
                        _make_subject("child", tests=[
                            _make_test_result("child_test", 40.0),
                        ]),
                    ],
                    tests=[
                        _make_test_result("parent_direct_test", 75.0),
                    ],
                ),
            ]),
        )

        results = list(tree.iter_test_results())
        paths = [path for path, _ in results]

        assert len(results) == 2
        assert paths[0] == "base/parent/child/child_test"
        assert paths[1] == "base/parent/parent_direct_test"

    def test_empty_tree_no_tests(self):
        """Tree with categories but no tests yields nothing."""
        tree = _make_tree(
            base=_make_category("base", subjects=[
                _make_subject("empty_subject"),
            ]),
        )

        results = list(tree.iter_test_results())
        assert not results

    def test_empty_base_no_subjects_no_tests(self):
        """Completely empty base category."""
        tree = _make_tree(base=_make_category("base"))

        results = list(tree.iter_test_results())
        assert not results

    def test_yields_actual_test_result_nodes(self):
        """Verify that yielded nodes are the original TestResultNode objects."""
        test = _make_test_result("identity_check", 88.0)
        tree = _make_tree(
            base=_make_category("base", subjects=[
                _make_subject("s", tests=[test]),
            ]),
        )

        results = list(tree.iter_test_results())
        assert results[0][1] is test  # Same object, not a copy

    def test_ordering_matches_tree_traversal(self):
        """Results iterate in tree order: categories in base→bonus→penalty,
        then subjects in declaration order, then tests in declaration order."""
        tree = _make_tree(
            base=_make_category("base", subjects=[
                _make_subject("alpha", tests=[
                    _make_test_result("a1", 10.0),
                    _make_test_result("a2", 20.0),
                ]),
                _make_subject("beta", tests=[
                    _make_test_result("b1", 30.0),
                ]),
            ]),
            bonus=_make_category("bonus", weight=10, tests=[
                _make_test_result("bonus_t", 100.0),
            ]),
        )

        paths = [path for path, _ in tree.iter_test_results()]
        assert paths == [
            "base/alpha/a1",
            "base/alpha/a2",
            "base/beta/b1",
            "bonus/bonus_t",
        ]


# ---------------------------------------------------------------------------
# to_score_vector() tests
# ---------------------------------------------------------------------------

class TestToScoreVector:
    """Tests for ResultTree.to_score_vector()."""

    def test_returns_dict_of_path_to_score(self):
        """Basic score vector output."""
        tree = _make_tree(
            base=_make_category("base", subjects=[
                _make_subject("code_quality", subjects=[
                    _make_subject("complexity", tests=[
                        _make_test_result("cyclomatic_complexity", 72.0),
                    ]),
                    _make_subject("documentation", tests=[
                        _make_test_result("docstring_coverage", 88.0),
                    ]),
                ]),
                _make_subject("test_coverage", tests=[
                    _make_test_result("test_inclusion", 60.0),
                ]),
            ]),
            bonus=_make_category("bonus", weight=10, subjects=[
                _make_subject("architecture", tests=[
                    _make_test_result("design_pattern_usage", 95.0),
                ]),
            ]),
            penalty=_make_category("penalty", weight=20, subjects=[
                _make_subject("hygiene", tests=[
                    _make_test_result("code_duplication", 45.0),
                ]),
            ]),
        )

        vector = tree.to_score_vector()

        assert vector == {
            "base/code_quality/complexity/cyclomatic_complexity": 72.0,
            "base/code_quality/documentation/docstring_coverage": 88.0,
            "base/test_coverage/test_inclusion": 60.0,
            "bonus/architecture/design_pattern_usage": 95.0,
            "penalty/hygiene/code_duplication": 45.0,
        }

    def test_empty_tree_returns_empty_dict(self):
        """Empty tree produces empty score vector."""
        tree = _make_tree(base=_make_category("base"))
        assert tree.to_score_vector() == {}

    def test_includes_passing_tests(self):
        """Score vector retains tests with score 100 (unlike Focus)."""
        tree = _make_tree(
            base=_make_category("base", subjects=[
                _make_subject("s", tests=[
                    _make_test_result("passing_test", 100.0),
                    _make_test_result("failing_test", 30.0),
                ]),
            ]),
        )

        vector = tree.to_score_vector()

        assert "base/s/passing_test" in vector
        assert vector["base/s/passing_test"] == 100.0
        assert vector["base/s/failing_test"] == 30.0

    def test_preserves_raw_scores(self):
        """Scores are raw floats, not weighted or rounded."""
        tree = _make_tree(
            base=_make_category("base", subjects=[
                _make_subject("s", tests=[
                    _make_test_result("precise_score", 72.333),
                ]),
            ]),
        )

        vector = tree.to_score_vector()
        assert vector["base/s/precise_score"] == 72.333

    def test_score_vector_keys_are_strings(self):
        """All keys are strings, all values are floats."""
        tree = _make_tree(
            base=_make_category("base", tests=[
                _make_test_result("t1", 50.0),
                _make_test_result("t2", 75.5),
            ]),
        )

        vector = tree.to_score_vector()
        for key, value in vector.items():
            assert isinstance(key, str), f"Key {key!r} is not a string"
            assert isinstance(value, float), f"Value {value!r} is not a float"

    def test_score_vector_matches_iter_test_results(self):
        """to_score_vector() is consistent with iter_test_results()."""
        tree = _make_tree(
            base=_make_category("base", subjects=[
                _make_subject("a", tests=[
                    _make_test_result("t1", 10.0),
                    _make_test_result("t2", 20.0),
                ]),
            ]),
            bonus=_make_category("bonus", weight=5, tests=[
                _make_test_result("bt", 100.0),
            ]),
        )

        vector = tree.to_score_vector()
        iter_dict = {path: node.score for path, node in tree.iter_test_results()}

        assert vector == iter_dict
