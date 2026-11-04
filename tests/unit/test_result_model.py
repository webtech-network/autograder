"""Self-contained assessed results and one scoring definition (ARC-11).

Golden cases are computed by hand from the documented arithmetic (OUTCOMES.md):
sibling weights are ratios, all-zero siblings share equally, a mixed holder
splits 100 by ``subjects_weight``, holder scores are weighted means of unrounded
child scores, final = base + bonus/100*cap - (100-penalty)/100*cap clamped to
0-100, and reported scores are rounded to two decimals (weights are not).
"""
import dataclasses
import inspect
from pathlib import Path

import pytest
from pydantic import BaseModel

from autograder import (
    EvaluationInput, Submission, SubmissionFile, Template, TestFunction, TestResult, build_pipeline,
)
from autograder.models.contracts import scoring
from autograder.models.contracts.outcome import ResultOutcomeTree, TestOutcome, score_vector
from autograder.models.contracts.verification import OutcomeStructureError, verify_outcome_tree
from autograder.models.criteria_tree import TestNode
from autograder.models.contracts.comparison import compare_outcomes

ROOT = Path(__file__).resolve().parents[2]


class Fixed(TestFunction):
    """Returns the configured score: the tree arithmetic is the subject under test."""
    name = "fixed"
    description = "Fixed score."

    def execute(self, evaluation: EvaluationInput, *, score: float) -> TestResult:
        return TestResult(self.name, score, f"scored {score}")


class Local(Template):
    template_name = "Local"
    template_description = "Fixed scores."
    requires_sandbox = False

    def __init__(self):
        self.tests = {"fixed": Fixed()}


def t(identity, score, weight=1, name=None, **extra):
    return {"id": identity, "type": "fixed", "name": name or identity, "weight": weight,
            "parameters": {"score": score}, **extra}


def s(name, weight, *, tests=(), subjects=(), subjects_weight=None):
    value = {"subject_name": name, "weight": weight}
    if tests:
        value["tests"] = list(tests)
    if subjects:
        value["subjects"] = list(subjects)
    if subjects_weight is not None:
        value["subjects_weight"] = subjects_weight
    return value


def run(base, bonus=None, penalty=None, feedback=None):
    criteria = {"base": {"weight": 100, **base}}
    if bonus:
        criteria["bonus"] = bonus
    if penalty:
        criteria["penalty"] = penalty
    definition = {"schema_version": "1.0", "templates": ["local"], "languages": ["python"], "criteria": criteria}
    if feedback:
        definition["feedback"] = feedback
    pipeline = build_pipeline(definition=definition, templates={"local": Local()})
    outcome = pipeline.run(Submission("u", "u", "a", {"main.py": SubmissionFile("main.py", "")})).outcome
    assert outcome.status == "completed", outcome.error
    return pipeline, outcome


def weights(holder):
    """(name, effective weight, score); weights compared with float tolerance, never rounded."""
    return [(child.name, pytest.approx(child.weight, abs=1e-9), child.score)
            for child in (*holder.subjects, *holder.tests)]


# --- Golden scoring cases -------------------------------------------------------

def test_nested_subjects():
    _, outcome = run({"subjects": [
        s("A", 1, subjects=[s("A1", 1, tests=[t("a1", 100)]), s("A2", 3, tests=[t("a2", 0)])]),
        s("B", 3, tests=[t("b1", 50), t("b2", 100)]),
    ]})
    base = outcome.tree.base
    assert weights(base) == [("A", 25, 25), ("B", 75, 75)]
    assert weights(base.subjects[0]) == [("A1", 25, 100), ("A2", 75, 0)]
    assert weights(base.subjects[1]) == [("b1", 50, 50), ("b2", 50, 100)]
    assert outcome.score == base.score == 62.5


@pytest.mark.parametrize("split,score,expected", [
    (30, 43.75, [("S", 30, 0), ("d1", 17.5, 100), ("d2", 52.5, 50)]),
    (0, 62.5, [("S", 0, 0), ("d1", 25, 100), ("d2", 75, 50)]),
    (100, 0, [("S", 100, 0), ("d1", 0, 100), ("d2", 0, 50)]),
])
def test_mixed_group_subjects_weight(split, score, expected):
    _, outcome = run({"subjects_weight": split, "subjects": [s("S", 1, tests=[t("s1", 0)])],
                      "tests": [t("d1", 100, 1), t("d2", 50, 3)]})
    assert weights(outcome.tree.base) == expected
    assert outcome.score == score


def test_zero_weight_siblings():
    _, outcome = run({"subjects": [s("Some zero", 1, tests=[t("z", 0, 0), t("n", 100, 2)]),
                                   s("All zero", 1, tests=[t("a", 0, 0), t("b", 100, 0)])]})
    assert weights(outcome.tree.base.subjects[0]) == [("z", 0, 0), ("n", 100, 100)]
    assert weights(outcome.tree.base.subjects[1]) == [("a", 50, 0), ("b", 50, 100)]
    assert outcome.score == 75


@pytest.mark.parametrize("base,bonus,penalty,final", [
    (80, (10, 50), (20, 75), 80),     # 80 + 5 - 5
    (100, (30, 100), None, 100),      # 130 clamps to 100
    (10, None, (50, 0), 0),           # -40 clamps to 0
    (60, (25, 0), (40, 100), 60),     # a missed bonus and a fully met penalty change nothing
])
def test_bonus_and_penalty_caps_and_clamping(base, bonus, penalty, final):
    _, outcome = run({"tests": [t("base", base)]},
                     bonus={"weight": bonus[0], "tests": [t("bonus", bonus[1])]} if bonus else None,
                     penalty={"weight": penalty[0], "tests": [t("penalty", penalty[1])]} if penalty else None)
    assert outcome.score == final
    if bonus:
        assert (outcome.tree.bonus.weight, outcome.tree.bonus.score) == bonus
    if penalty:
        assert (outcome.tree.penalty.weight, outcome.tree.penalty.score) == penalty


def test_documented_rounding():
    """Leaf and holder scores are rounded for reporting; weights are not; holders use unrounded scores."""
    _, outcome = run({"tests": [t("third", 100 / 3), t("two-thirds", 200 / 3), t("x", 100 / 3)]})
    tests = outcome.tree.base.tests
    assert [test.score for test in tests] == [33.33, 66.67, 33.33]
    assert [test.weight for test in tests] == [100 / 3] * 3
    # (100/3 + 200/3 + 100/3) / 3 = 44.444...; summing the rounded leaves would also give 44.44.
    assert outcome.tree.base.score == outcome.score == 44.44
    _, outcome = run({"tests": [t("a", 0.005, 1), t("b", 0.004, 1)]})
    assert [test.score for test in outcome.tree.base.tests] == [round(0.005, 2), 0.0]
    assert outcome.score == round((0.005 + 0.004) / 2, 2)


# --- Self-contained results and round trips ------------------------------------

def test_results_own_their_data_and_round_trip_completely():
    _, outcome = run({"tests": [t("targeted", 40, file="main.py"), t("plain", 100)]})
    tree = outcome.tree
    leaf = tree.base.tests[0]
    assert (leaf.id, leaf.evaluator, leaf.name, leaf.file_target, leaf.parameters, leaf.report) == (
        "targeted", "fixed", "targeted", ("main.py",), {"score": 40}, "scored 40.0")
    serialized = tree.model_dump(mode="json")
    assert serialized["base"]["tests"][0]["file_target"] == ["main.py"]
    restored = ResultOutcomeTree.model_validate(serialized)
    assert restored == tree and restored.model_dump(mode="json") == serialized

    def live_references(value):
        if isinstance(value, (TestNode, TestFunction)):
            yield value
        elif isinstance(value, BaseModel):
            for name in type(value).model_fields:
                yield from live_references(getattr(value, name))
        elif isinstance(value, dict):
            for item in value.values():
                yield from live_references(item)
        elif isinstance(value, (list, tuple)):
            for item in value:
                yield from live_references(item)
    assert not list(live_references(tree))


def test_evaluator_results_are_plain_frozen_values():
    assert [field.name for field in dataclasses.fields(TestResult)] == ["test_name", "score", "report"]
    with pytest.raises(dataclasses.FrozenInstanceError):
        TestResult("x", 1, "").score = 2


# --- One weight/traversal definition, shared by grading and verification ----------

def test_weight_arithmetic_has_one_definition():
    definers = [path for path in (ROOT / "autograder").rglob("*.py") if "def normalized_sibling_weights" in path.read_text()]
    assert definers == [ROOT / "autograder/models/contracts/scoring.py"]
    route_code = (ROOT / "web/service/submission_operations.py").read_text()
    for name in ("normalized_sibling_weights", "subjects_weight", "isclose"):
        assert name not in route_code
    assert "child_weights" in inspect.getsource(verify_outcome_tree.__globals__["_verify_holder"])
    from autograder.services import grading  # pylint: disable=import-outside-toplevel
    assert grading.child_weights is scoring.child_weights


@pytest.mark.parametrize("case", ["nested", "mixed", "zero", "caps"])
def test_locally_graded_trees_pass_the_shared_structural_check(case):
    base = {
        "nested": {"subjects": [s("A", 1, subjects=[s("A1", 1, tests=[t("a1", 100)])]), s("B", 3, tests=[t("b", 0)])]},
        "mixed": {"subjects_weight": 30, "subjects": [s("S", 1, tests=[t("s1", 0)])], "tests": [t("d1", 100)]},
        "zero": {"tests": [t("z", 0, 0), t("n", 100, 0)]},
        "caps": {"tests": [t("base", 50)]},
    }[case]
    pipeline, outcome = run(base, bonus={"weight": 10, "tests": [t("bonus", 100)]} if case == "caps" else None)
    verify_outcome_tree(pipeline.compiled.criteria_tree, outcome.tree)
    tampered = outcome.tree.model_dump(mode="json")
    if tampered["base"].get("subjects"):
        tampered["base"]["subjects"][0]["name"] = "Moved"
    else:
        tampered["base"]["tests"][0]["name"] = "Renamed"
    with pytest.raises(OutcomeStructureError):
        verify_outcome_tree(pipeline.compiled.criteria_tree, ResultOutcomeTree.model_validate(tampered))


# --- Duplicate labels and slashes never collide --------------------------------

def test_duplicate_labels_and_slashes_stay_distinct_in_vectors_feedback_and_comparison():
    label = "Group / check"
    feedback = {"enabled": True, "preferences": {"general": {"show_passed_tests": True, "online_content": [
        {"url": "https://example.com/failing", "description": "For failing", "linked_tests": ["failing"]},
        {"url": "https://example.com/passing", "description": "For passing", "linked_tests": ["passing"]}]}}}
    head_pipeline, head = run({"subjects": [s("A / B", 1, tests=[t("failing", 0, name=label), t("passing", 100, name=label)]),
                                s("A / B", 1, tests=[t("other", 50, name=label)])]}, feedback=feedback)
    assert score_vector(head.tree) == {"failing": 0, "passing": 100, "other": 50}
    content = head.feedback.content
    assert content.count(f"### 🧪 {label}") == 3
    assert "https://example.com/failing" in content and "https://example.com/passing" not in content
    baseline_pipeline, baseline = run({"subjects": [s("A / B", 1, tests=[t("failing", 100, name=label), t("passing", 100, name=label)]),
                                    s("A / B", 1, tests=[t("other", 50, name=label)])]})
    comparison = compare_outcomes(baseline, head, baseline_pipeline.compiled, head_pipeline.compiled)
    # The fixture evaluator's score is a parameter, so "failing" is redefined across revisions;
    # identity, labels and per-side scores still join strictly by criterion ID.
    assert [(row.criterion_id, row.baseline_score, row.head_score, row.head_label) for row in comparison.criteria] == [
        ("failing", 100, 0, label), ("passing", 100, 100, label), ("other", 50, 50, label)]
    assert {row.criterion_id: row.status for row in comparison.criteria} == {
        "failing": "redefined", "passing": "unchanged", "other": "unchanged"}


def test_traversal_order_is_shared():
    _, outcome = run({"subjects_weight": 50, "subjects": [s("S", 1, tests=[t("nested", 0)])], "tests": [t("direct", 0)]})
    assert [test.id for _, test in scoring.iter_tests(outcome.tree)] == ["nested", "direct"]
    assert isinstance(next(scoring.iter_tests(outcome.tree))[1], TestOutcome)


def test_focus_impact_applies_each_effective_weight_once():
    """Regression: the old focus traversal applied a mixed group's subjects_weight twice."""
    from autograder.services.focus_service import find_focus  # pylint: disable=import-outside-toplevel
    _, outcome = run({"subjects": [
        s("Program", 3, tests=[t("program", 0)]),
        s("Quality", 1, subjects_weight=60, subjects=[s("Imports", 1, tests=[t("imports", 0)])],
          tests=[t("artifact", 0)]),
    ]})
    focus = find_focus(outcome.tree)
    # Shares of the final score: 75, 25*0.6 = 15 and 25*0.4 = 10 (previously 9 and 4).
    assert [(item.test_result.id, pytest.approx(item.diff_score)) for item in focus.base] == [
        ("program", 75), ("imports", 15), ("artifact", 10)]
    assert sum(item.diff_score for item in focus.base) == pytest.approx(100 - outcome.score)
