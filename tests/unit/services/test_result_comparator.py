"""
Unit tests for ResultComparator and ResultTree.from_dict().

Tests cover:
1. Equal trees (score_delta = 0, improved = False, status = unchanged)
2. Score improvements (score_delta > 0, improved = True, status = improved)
3. Score regressions (score_delta < 0, improved = False, status = regressed)
4. Introduced tests (in head, not in baseline -> status = introduced)
5. Removed tests (in baseline, not in head -> status = removed)
6. Complex mixed trees with multiple categories and nested subjects
7. ResultTree.from_dict() deserialization and round-trip verification
8. ComparisonResult and TestDelta serialization
"""

from autograder.models.dataclass.comparison_result import ComparisonResult, TestDelta
from autograder.models.result_tree import (
    CategoryResultNode,
    ResultTree,
    RootResultNode,
    SubjectResultNode,
    TestResultNode,
)
from autograder.services.result_comparator import ResultComparator


# ---------------------------------------------------------------------------
# Test Helpers
# ---------------------------------------------------------------------------


def _make_test(name: str, score: float, weight: float = 100.0) -> TestResultNode:
    return TestResultNode(
        name=name,
        score=score,
        report=f"Report for {name}",
        test_node=None,
        weight=weight,
    )


def _make_subject(
    name: str,
    tests=None,
    subjects=None,
    weight: float = 100.0,
    score: float = 100.0,
) -> SubjectResultNode:
    return SubjectResultNode(
        name=name,
        weight=weight,
        score=score,
        subjects=subjects or [],
        tests=tests or [],
    )


def _make_category(
    name: str,
    subjects=None,
    tests=None,
    weight: float = 100.0,
    score: float = 100.0,
) -> CategoryResultNode:
    return CategoryResultNode(
        name=name,
        weight=weight,
        score=score,
        subjects=subjects or [],
        tests=tests or [],
    )


def _make_tree(
    base: CategoryResultNode,
    bonus: CategoryResultNode = None,
    penalty: CategoryResultNode = None,
    final_score: float = 100.0,
) -> ResultTree:
    root = RootResultNode(name="root", score=final_score, base=base, bonus=bonus, penalty=penalty)
    return ResultTree(root=root)


# ---------------------------------------------------------------------------
# Test Cases
# ---------------------------------------------------------------------------


class TestResultComparator:
    """Test suite for ResultComparator logic."""

    def test_identical_trees_produce_unchanged_status(self):
        """Verify identical trees return 0 delta and unchanged status."""
        t1 = _make_test("t1", 100.0)
        base = _make_category("base", subjects=[_make_subject("s1", tests=[t1])])
        tree_a = _make_tree(base=base, final_score=100.0)
        tree_b = _make_tree(base=base, final_score=100.0)

        result = ResultComparator.compare(baseline=tree_a, head=tree_b)

        assert result.score_delta == 0.0
        assert result.improved is False
        assert len(result.test_deltas) == 1
        delta = result.test_deltas[0]
        assert delta.path == "base/s1/t1"
        assert delta.status == "unchanged"
        assert delta.baseline_score == 100.0
        assert delta.head_score == 100.0
        assert delta.delta == 0.0

    def test_score_improvement(self):
        """Verify score improvement returns positive delta and improved status."""
        baseline_test = _make_test("t1", 60.0)
        head_test = _make_test("t1", 90.0)

        baseline_tree = _make_tree(
            base=_make_category("base", subjects=[_make_subject("s1", tests=[baseline_test])]),
            final_score=60.0,
        )
        head_tree = _make_tree(
            base=_make_category("base", subjects=[_make_subject("s1", tests=[head_test])]),
            final_score=90.0,
        )

        result = ResultComparator.compare(baseline=baseline_tree, head=head_tree)

        assert result.score_delta == 30.0
        assert result.improved is True
        assert len(result.test_deltas) == 1
        delta = result.test_deltas[0]
        assert delta.path == "base/s1/t1"
        assert delta.status == "improved"
        assert delta.baseline_score == 60.0
        assert delta.head_score == 90.0
        assert delta.delta == 30.0

    def test_score_regression(self):
        """Verify score regression returns negative delta and regressed status."""
        baseline_test = _make_test("t1", 100.0)
        head_test = _make_test("t1", 40.0)

        baseline_tree = _make_tree(
            base=_make_category("base", subjects=[_make_subject("s1", tests=[baseline_test])]),
            final_score=100.0,
        )
        head_tree = _make_tree(
            base=_make_category("base", subjects=[_make_subject("s1", tests=[head_test])]),
            final_score=40.0,
        )

        result = ResultComparator.compare(baseline=baseline_tree, head=head_tree)

        assert result.score_delta == -60.0
        assert result.improved is False
        assert len(result.test_deltas) == 1
        delta = result.test_deltas[0]
        assert delta.path == "base/s1/t1"
        assert delta.status == "regressed"
        assert delta.baseline_score == 100.0
        assert delta.head_score == 40.0
        assert delta.delta == -60.0

    def test_introduced_test(self):
        """Verify new test in head returns introduced status."""
        t1 = _make_test("t1", 80.0)
        t2 = _make_test("t2", 100.0)

        baseline_tree = _make_tree(
            base=_make_category("base", subjects=[_make_subject("s1", tests=[t1])]),
            final_score=80.0,
        )
        head_tree = _make_tree(
            base=_make_category("base", subjects=[_make_subject("s1", tests=[t1, t2])]),
            final_score=90.0,
        )

        result = ResultComparator.compare(baseline=baseline_tree, head=head_tree)

        assert len(result.test_deltas) == 2
        d1, d2 = result.test_deltas
        assert d1.path == "base/s1/t1"
        assert d1.status == "unchanged"

        assert d2.path == "base/s1/t2"
        assert d2.status == "introduced"
        assert d2.baseline_score is None
        assert d2.head_score == 100.0
        assert d2.delta is None

    def test_removed_test(self):
        """Verify removed test from baseline returns removed status."""
        t1 = _make_test("t1", 80.0)
        t2 = _make_test("t2", 50.0)

        baseline_tree = _make_tree(
            base=_make_category("base", subjects=[_make_subject("s1", tests=[t1, t2])]),
            final_score=65.0,
        )
        head_tree = _make_tree(
            base=_make_category("base", subjects=[_make_subject("s1", tests=[t1])]),
            final_score=80.0,
        )

        result = ResultComparator.compare(baseline=baseline_tree, head=head_tree)

        assert len(result.test_deltas) == 2
        d1, d2 = result.test_deltas
        assert d1.path == "base/s1/t1"
        assert d1.status == "unchanged"

        assert d2.path == "base/s1/t2"
        assert d2.status == "removed"
        assert d2.baseline_score == 50.0
        assert d2.head_score is None
        assert d2.delta is None

    def test_complex_tree_mixed_statuses(self):
        """Verify complex tree with mixed transitions."""
        # Baseline tests
        b_t1 = _make_test("t1", 50.0)
        b_t2 = _make_test("t2", 100.0)
        b_t3 = _make_test("t3", 80.0)

        # Head tests
        h_t1 = _make_test("t1", 80.0)   # improved
        h_t2 = _make_test("t2", 40.0)   # regressed
        h_t4 = _make_test("t4", 100.0)  # introduced
        # b_t3 is removed

        baseline_tree = _make_tree(
            base=_make_category("base", subjects=[
                _make_subject("s1", tests=[b_t1, b_t2]),
                _make_subject("s2", tests=[b_t3]),
            ]),
            final_score=76.67,
        )
        head_tree = _make_tree(
            base=_make_category("base", subjects=[
                _make_subject("s1", tests=[h_t1, h_t2]),
                _make_subject("s2", tests=[h_t4]),
            ]),
            final_score=73.33,
        )

        result = ResultComparator.compare(baseline=baseline_tree, head=head_tree)

        assert result.score_delta == -3.34
        assert result.improved is False

        deltas = {d.path: d for d in result.test_deltas}

        assert deltas["base/s1/t1"].status == "improved"
        assert deltas["base/s1/t1"].delta == 30.0

        assert deltas["base/s1/t2"].status == "regressed"
        assert deltas["base/s1/t2"].delta == -60.0

        assert deltas["base/s2/t3"].status == "removed"
        assert deltas["base/s2/t3"].baseline_score == 80.0

        assert deltas["base/s2/t4"].status == "introduced"
        assert deltas["base/s2/t4"].head_score == 100.0


class TestResultTreeFromDict:
    """Test suite for ResultTree.from_dict deserialization."""

    def test_deserialization_round_trip(self):
        """Verify round trip serialization and deserialization."""
        t1 = _make_test("t1", 85.0)
        t2 = _make_test("t2", 95.0)
        cat_base = _make_category("base", subjects=[_make_subject("sub1", tests=[t1, t2])])
        original_tree = _make_tree(base=cat_base, final_score=90.0)

        tree_dict = original_tree.to_dict()
        reconstructed = ResultTree.from_dict(tree_dict)

        assert reconstructed.root.score == 90.0
        assert reconstructed.root.base.name == "base"
        assert len(reconstructed.root.base.subjects) == 1

        vector = reconstructed.to_score_vector()
        assert vector["base/sub1/t1"] == 85.0
        assert vector["base/sub1/t2"] == 95.0

    def test_deserialization_db_children_wrapper_format(self):
        """Verify deserialization from DB children wrapper format."""
        db_dict = {
            "final_score": 85.5,
            "children": {
                "name": "root",
                "score": 85.5,
                "base": {
                    "name": "base",
                    "weight": 100.0,
                    "score": 85.5,
                    "tests": [
                        {"name": "check_syntax", "score": 100.0, "weight": 50.0},
                        {"name": "check_logic", "score": 71.0, "weight": 50.0},
                    ],
                },
            },
        }

        reconstructed = ResultTree.from_dict(db_dict)
        assert reconstructed.root.score == 85.5
        vector = reconstructed.to_score_vector()
        assert vector["base/check_syntax"] == 100.0
        assert vector["base/check_logic"] == 71.0


class TestComparisonResultSerialization:
    """Test suite for ComparisonResult dataclass serialization."""

    def test_to_dict_format(self):
        """Verify to_dict output format for ComparisonResult."""
        delta = TestDelta(
            path="base/s1/t1",
            status="improved",
            baseline_score=50.0,
            head_score=80.0,
            delta=30.0,
        )
        res = ComparisonResult(score_delta=30.0, improved=True, test_deltas=[delta])

        d = res.to_dict()
        assert d["score_delta"] == 30.0
        assert d["improved"] is True
        assert len(d["test_deltas"]) == 1
        td = d["test_deltas"][0]
        assert td["path"] == "base/s1/t1"
        assert td["status"] == "improved"
        assert td["baseline_score"] == 50.0
        assert td["head_score"] == 80.0
        assert td["delta"] == 30.0
