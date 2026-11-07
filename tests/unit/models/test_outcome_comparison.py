"""Pure comparison of canonical outcomes: identity by criterion ID, explicit compatibility."""
from copy import deepcopy
import json

import pytest
from pydantic import ValidationError

from autograder import ComparisonError, OutcomeComparison, compare_outcomes, compile_definition
from autograder.models.contracts.comparison import CriterionComparison
from autograder.models.contracts.outcome import outcome_score_vector, validate_outcome
from autograder.models.contracts.definition import snapshot_hash
from autograder.models.contracts.scoring import normalized_sibling_weights
from autograder.services.definition_migration import upgrade_v1


def criterion(identity, *, name=None, imports=("os",), weight=100, file=None, type_="forbidden_import"):
    value = {"id": identity, "type": type_, "name": name or identity.title(), "weight": weight,
             "parameters": ({"forbidden_imports": list(imports)} if type_ == "forbidden_import"
                            else {"forbidden_keywords": ["for_loop"], "custom_ast_grep_rules": []})}
    if file:
        value["file"] = file
    return value


def definition(*tests, bonus=None, penalty=None, preparation=None, subjects=None, subjects_weight=None):
    base = {}
    if tests:
        base["tests"] = list(tests)
    if subjects:
        base["subjects"] = subjects
    if subjects_weight is not None:
        base["subjects_weight"] = subjects_weight
    value = {"schema_version": "2.0", "languages": ["python"],
             "criteria": {"base": base}}
    if bonus:
        value["criteria"]["bonus"] = bonus
    if penalty:
        value["criteria"]["penalty"] = penalty
    if preparation:
        value["preparation"] = preparation
    return compile_definition(value)


def build_outcome(compiled, scores, *, execution_id="execution", revision=None, reference=None, failed=False):
    """Build a valid canonical outcome for a compiled definition with chosen criterion scores."""
    provenance = {"schema_version": "2.0", "definition_hash": compiled.definition_hash,
                  "reference": reference, "revision": revision}
    value = {"schema_version": "1.0", "execution_id": execution_id, "language": "python",
             "provenance": provenance, "started_at": "2026-10-04T12:00:00Z",
             "finished_at": "2026-10-04T12:00:01Z", "duration_ms": 1000}
    if failed:
        return validate_outcome({**value, "status": "failed", "score": None, "tree": None, "error": {
            "code": "PROVIDER_ERROR", "message": "The provider failed.", "category": "provider",
            "retryable": True, "correlation_id": execution_id}})

    def holder(group, name, kind, weight):
        tests, subjects = group.tests or [], group.subjects or []
        if tests and subjects:
            test_weights = normalized_sibling_weights([t.weight for t in tests], (100 - group.subjects_weight) / 100)
            subject_weights = normalized_sibling_weights([s.weight for s in subjects], group.subjects_weight / 100)
        else:
            test_weights = normalized_sibling_weights([t.weight for t in tests])
            subject_weights = normalized_sibling_weights([s.weight for s in subjects])
        test_nodes = [{"id": t.id, "evaluator": t.type, "type": "test", "name": t.name, "score": float(scores[t.id]),
                       "weight": w, "report": "", "file_target": [t.file] if t.file else None,
                       "parameters": t.parameters} for t, w in zip(tests, test_weights)]
        subject_nodes = [holder(s, s.name, "subject", w) for s, w in zip(subjects, subject_weights)]
        children = test_nodes + subject_nodes
        score = sum(c["score"] * c["weight"] for c in children) / sum(c["weight"] for c in children)
        return {"name": name, "type": kind, "score": round(score, 2), "weight": weight,
                "tests": test_nodes, "subjects": subject_nodes}

    criteria = compiled.definition.criteria
    tree = {"name": "root", "type": "root"}
    total = 0.0
    for name in ("base", "bonus", "penalty"):
        category = getattr(criteria, name)
        if category is None:
            continue
        points = 100 if name == "base" else category.max_points
        node = holder(category, name, "category", points)
        tree[name] = node
        if name == "base":
            total += node["score"]
        elif name == "bonus":
            total += node["score"] / 100 * points
        else:
            total -= (100 - node["score"]) / 100 * points
    tree["score"] = round(min(100.0, max(0.0, total)), 2)
    return validate_outcome({**value, "status": "completed", "score": tree["score"], "tree": tree, "error": None})


def rows(comparison):
    return {row.criterion_id: row for row in comparison.criteria}


@pytest.mark.parametrize("before,after,status", [(50, 75, "improved"), (75, 50, "regressed"), (75, 75, "unchanged")])
def test_same_definition_reports_overall_and_criterion_deltas(before, after, status):
    compiled = definition(criterion("greeting"))
    result = compare_outcomes(build_outcome(compiled, {"greeting": before}),
                              build_outcome(compiled, {"greeting": after}), compiled, compiled)
    assert result.compatibility == "same_definition"
    assert result.score_delta == after - before
    assert result.improved is (after > before)
    assert result.changed_definition_sections == ()
    [row] = result.criteria
    assert (row.criterion_id, row.status, row.delta) == ("greeting", status, after - before)
    assert (row.baseline_score, row.head_score) == (before, after)
    assert row.baseline_weight == row.head_weight == 100


def test_same_definition_accepts_stored_json_snapshots_and_wire_outcomes():
    compiled = definition(criterion("a"), criterion("b", imports=["sys"]))
    snapshot = compiled.definition.model_dump(mode="json")
    before = build_outcome(compiled, {"a": 0, "b": 100}).model_dump(mode="json")
    after = build_outcome(compiled, {"a": 100, "b": 100}).model_dump(mode="json")
    copies = deepcopy((before, after, snapshot))
    first = compare_outcomes(before, after, snapshot, snapshot)
    assert first.score_delta == 50
    assert [(r.criterion_id, r.status) for r in first.criteria] == [("a", "improved"), ("b", "unchanged")]
    # Pure and deterministic: inputs are untouched and a retry gives the same result.
    assert (before, after, snapshot) == copies
    assert compare_outcomes(before, after, snapshot, snapshot) == first


def test_renamed_label_is_the_same_criterion_across_revisions():
    old = definition(criterion("greeting", name="Greeting"))
    new = definition(criterion("greeting", name="Welcome"))
    result = compare_outcomes(build_outcome(old, {"greeting": 60}, revision=1),
                              build_outcome(new, {"greeting": 80}, revision=2), old, new)
    assert result.compatibility == "cross_revision"
    assert result.score_delta is None and result.improved is None
    assert "not comparable as a whole" in result.explanation
    assert result.changed_definition_sections == ("criteria",)
    [row] = result.criteria
    assert (row.status, row.delta, row.baseline_label, row.head_label) == ("improved", 20, "Greeting", "Welcome")
    assert (result.baseline.provenance.revision, result.head.provenance.revision) == (1, 2)


def test_duplicate_labels_and_slashes_remain_distinct_by_id():
    compiled = definition(criterion("one", name="Quality/Imports"), criterion("two", name="Quality/Imports", imports=["sys"]))
    result = compare_outcomes(build_outcome(compiled, {"one": 0, "two": 100}),
                              build_outcome(compiled, {"one": 100, "two": 0}), compiled, compiled)
    assert [(r.criterion_id, r.status, r.head_label) for r in result.criteria] == [
        ("one", "improved", "Quality/Imports"), ("two", "regressed", "Quality/Imports")]
    assert result.score_delta == 0 and result.improved is False


def test_repeated_evaluator_types_are_distinct_criteria():
    compiled = definition(*(criterion(f"imports-{index}", name="Imports", imports=[module])
                            for index, module in enumerate(["os", "sys", "re"])))
    scores = {"imports-0": 0, "imports-1": 50, "imports-2": 100}
    result = compare_outcomes(build_outcome(compiled, scores),
                              build_outcome(compiled, {**scores, "imports-1": 100}), compiled, compiled)
    assert [r.status for r in result.criteria] == ["unchanged", "improved", "unchanged"]


def test_reordered_and_regrouped_labels_keep_identity_and_weight():
    old = definition(criterion("a"), criterion("b", imports=["sys"]))
    subjects = [{"name": "Renamed group", "weight": 1, "tests": [criterion("b", name="New B", imports=["sys"]),
                                                                       criterion("a", name="New A")]}]
    new = definition(subjects=subjects)
    result = compare_outcomes(build_outcome(old, {"a": 0, "b": 100}),
                              build_outcome(new, {"a": 100, "b": 100}), old, new)
    assert result.compatibility == "cross_revision"
    assert [(r.criterion_id, r.status) for r in result.criteria] == [("b", "unchanged"), ("a", "improved")]
    assert rows(result)["a"].head_label == "New A"


def test_added_and_removed_criteria_are_explicit():
    old = definition(criterion("kept"), criterion("removed", imports=["sys"]))
    new = definition(criterion("kept"), criterion("introduced", imports=["re"]))
    result = compare_outcomes(build_outcome(old, {"kept": 0, "removed": 40}),
                              build_outcome(new, {"kept": 0, "introduced": 70}), old, new)
    assert [(r.criterion_id, r.status) for r in result.criteria] == [
        ("kept", "unchanged"), ("introduced", "introduced"), ("removed", "removed")]
    introduced, removed = rows(result)["introduced"], rows(result)["removed"]
    assert (introduced.baseline_score, introduced.head_score, introduced.delta) == (None, 70, None)
    assert (removed.baseline_score, removed.head_score, removed.delta) == (40, None, None)
    assert removed.baseline_label == "Removed" and removed.head_label is None
    assert result.score_delta is None


def test_changed_parameters_are_redefined_without_delta():
    old = definition(criterion("imports", imports=["os"]))
    new = definition(criterion("imports", imports=["os", "sys"]))
    [row] = compare_outcomes(build_outcome(old, {"imports": 100}),
                             build_outcome(new, {"imports": 0}), old, new).criteria
    assert (row.status, row.baseline_score, row.head_score, row.delta) == ("redefined", 100, 0, None)


def test_changed_evaluator_type_with_same_id_is_redefined():
    old = definition(criterion("rule"))
    new = definition(criterion("rule", type_="forbidden_keyword"))
    [row] = compare_outcomes(build_outcome(old, {"rule": 100}), build_outcome(new, {"rule": 100}), old, new).criteria
    assert row.status == "redefined" and row.delta is None


def test_changed_file_target_is_redefined():
    old = definition(criterion("imports", file="main.py"))
    new = definition(criterion("imports", file="src/main.py"))
    [row] = compare_outcomes(build_outcome(old, {"imports": 50}), build_outcome(new, {"imports": 50}), old, new).criteria
    assert row.status == "redefined" and row.delta is None


def test_changed_weights_are_reweighted_with_criterion_delta():
    old = definition(criterion("a", weight=1), criterion("b", weight=1, imports=["sys"]))
    new = definition(criterion("a", weight=3), criterion("b", weight=1, imports=["sys"]))
    result = compare_outcomes(build_outcome(old, {"a": 50, "b": 100}),
                              build_outcome(new, {"a": 75, "b": 100}), old, new)
    a, b = rows(result)["a"], rows(result)["b"]
    # Both siblings' shares changed, so neither retains its former grading meaning exactly.
    assert (a.status, a.delta, a.baseline_weight, a.head_weight) == ("reweighted", 25, 50, 75)
    assert (b.status, b.delta, b.baseline_weight, b.head_weight) == ("reweighted", 0, 50, 25)
    assert result.score_delta is None


def test_proportional_weight_rescaling_is_not_a_reweight():
    old = definition(criterion("a", weight=1), criterion("b", weight=1, imports=["sys"]))
    new = definition(criterion("a", weight=50), criterion("b", weight=50, imports=["sys"]))
    result = compare_outcomes(build_outcome(old, {"a": 0, "b": 0}), build_outcome(new, {"a": 100, "b": 0}), old, new)
    assert [r.status for r in result.criteria] == ["improved", "unchanged"]


def test_moving_a_criterion_to_bonus_is_a_placement_change():
    old = definition(criterion("a"), criterion("extra", imports=["sys"]))
    new = definition(criterion("a"), bonus={"max_points": 10, "tests": [criterion("extra", imports=["sys"])]})
    row = rows(compare_outcomes(build_outcome(old, {"a": 100, "extra": 100}),
                                build_outcome(new, {"a": 100, "extra": 100}), old, new))["extra"]
    assert (row.status, row.baseline_category, row.head_category, row.delta) == ("reweighted", "base", "bonus", 0)
    assert (row.baseline_weight, row.head_weight) == (50, 10)


def test_changed_category_cap_reweights_its_criteria():
    old = definition(criterion("a"), penalty={"max_points": 10, "tests": [criterion("late", imports=["sys"])]})
    new = definition(criterion("a"), penalty={"max_points": 20, "tests": [criterion("late", imports=["sys"])]})
    row = rows(compare_outcomes(build_outcome(old, {"a": 100, "late": 0}),
                                build_outcome(new, {"a": 100, "late": 0}), old, new))["late"]
    assert (row.status, row.baseline_weight, row.head_weight) == ("reweighted", 10, 20)


def test_mixed_group_split_change_reweights():
    def mixed(split):
        return definition(criterion("direct"), subjects=[{"name": "Group", "weight": 1,
                          "tests": [criterion("nested", imports=["sys"])]}], subjects_weight=split)
    old, new = mixed(25), mixed(50)
    result = compare_outcomes(build_outcome(old, {"direct": 100, "nested": 0}),
                              build_outcome(new, {"direct": 100, "nested": 0}), old, new)
    assert {r.criterion_id: (r.status, r.baseline_weight, r.head_weight) for r in result.criteria} == {
        "direct": ("reweighted", 75, 50), "nested": ("reweighted", 25, 50)}


def test_non_criteria_changes_are_cross_revision_without_overall_delta():
    old = definition(criterion("a"))
    new = definition(criterion("a"), preparation={"languages": {"python": {"required_files": ["main.py"]}}})
    result = compare_outcomes(build_outcome(old, {"a": 0}), build_outcome(new, {"a": 100}), old, new)
    assert result.compatibility == "cross_revision"
    assert result.changed_definition_sections == ("preparation",)
    assert result.score_delta is None
    assert [(r.status, r.delta) for r in result.criteria] == [("improved", 100)]


@pytest.mark.parametrize("side", ["baseline", "head"])
def test_failed_outcomes_have_no_comparable_grade(side):
    compiled = definition(criterion("a"))
    good, bad = build_outcome(compiled, {"a": 0}), build_outcome(compiled, {}, failed=True)
    args = (bad, good) if side == "baseline" else (good, bad)
    with pytest.raises(ComparisonError) as error:
        compare_outcomes(*args, compiled, compiled)
    assert (error.value.code, error.value.side) == ("OUTCOME_NOT_COMPLETED", side)


def test_definition_must_be_the_one_bound_to_the_outcome():
    compiled = definition(criterion("a"))
    other = definition(criterion("a", imports=["sys"]))
    with pytest.raises(ComparisonError) as error:
        compare_outcomes(build_outcome(compiled, {"a": 0}), build_outcome(compiled, {"a": 0}), other, compiled)
    assert (error.value.code, error.value.side) == ("DEFINITION_MISMATCH", "baseline")


def test_tree_criteria_must_match_bound_definition():
    compiled = definition(criterion("a"))
    wire = build_outcome(compiled, {"a": 0}).model_dump(mode="json")
    wire["tree"]["base"]["tests"][0]["id"] = "guessed"
    with pytest.raises(ComparisonError) as error:
        compare_outcomes(wire, wire, compiled, compiled)
    assert error.value.code == "DEFINITION_MISMATCH"


@pytest.mark.parametrize("mutate", [
    lambda wire: wire.update(score_vector={"a": 100}),
    lambda wire: wire["tree"]["base"]["tests"][0].pop("id"),
    lambda wire: wire.update(score=100),
])
def test_independent_vectors_and_legacy_or_inconsistent_trees_are_rejected(mutate):
    compiled = definition(criterion("a"))
    wire = build_outcome(compiled, {"a": 0}).model_dump(mode="json")
    mutate(wire)
    with pytest.raises(ComparisonError) as error:
        compare_outcomes(wire, wire, compiled, compiled)
    assert error.value.code == "INVALID_OUTCOME"


def test_invalid_definition_is_reported():
    compiled = definition(criterion("a"))
    outcome = build_outcome(compiled, {"a": 0})
    with pytest.raises(ComparisonError) as error:
        compare_outcomes(outcome, outcome, {"schema_version": "0.9"}, compiled)
    assert error.value.code == "INVALID_DEFINITION"


def test_vectors_are_derived_from_authoritative_trees():
    compiled = definition(criterion("a"), criterion("b", imports=["sys"]))
    before, after = build_outcome(compiled, {"a": 10, "b": 20}), build_outcome(compiled, {"a": 30, "b": 20})
    result = compare_outcomes(before, after, compiled, compiled)
    assert {r.criterion_id: r.baseline_score for r in result.criteria} == outcome_score_vector(before)
    assert {r.criterion_id: r.head_score for r in result.criteria} == outcome_score_vector(after)


def test_result_models_reject_inconsistent_content():
    compiled = definition(criterion("a"))
    value = compare_outcomes(build_outcome(compiled, {"a": 0}), build_outcome(compiled, {"a": 100}),
                             compiled, compiled).model_dump(mode="json")
    for mutate in (lambda v: v.update(score_delta=None),
                   lambda v: v.update(improved=False),
                   lambda v: v.update(compatibility="cross_revision"),
                   lambda v: v["criteria"][0].update(status="reweighted"),
                   lambda v: v.update(criteria=v["criteria"] * 2)):
        broken = deepcopy(value)
        mutate(broken)
        with pytest.raises(ValidationError):
            OutcomeComparison.model_validate(broken)
    side = {"baseline_label": "A", "baseline_score": 0.0, "baseline_category": "base", "baseline_weight": 100.0}
    head = {"head_label": "A", "head_score": 50.0, "head_category": "base", "head_weight": 100.0}
    for invalid in ({"status": "introduced", **side, **head},
                    {"status": "removed", **head},
                    {"status": "redefined", **side, **head, "delta": 50.0},
                    {"status": "reweighted", **side, **head},
                    {"status": "improved", **side, **head, "delta": 10.0},
                    {"status": "unchanged", "baseline_label": "A", **head, "delta": 0.0}):
        with pytest.raises(ValidationError):
            CriterionComparison(criterion_id="a", **invalid)
    assert json.loads(OutcomeComparison.model_validate(value).model_dump_json()) == value


def test_real_engine_outcomes_compare_without_regrading():
    from autograder import build_pipeline
    from tests.unit.pipeline.test_terminal_outcome import submission
    compiled = definition(criterion("imports"))
    pipeline = build_pipeline(definition=compiled)
    before, after = pipeline.run(submission("import os")).outcome, pipeline.run(submission("print(1)")).outcome
    result = compare_outcomes(before, after, compiled.definition, compiled.definition)
    assert (result.score_delta, result.criteria[0].status) == (100, "improved")
    assert (result.baseline.execution_id, result.head.execution_id) == (before.execution_id, after.execution_id)
    assert before.comparison.status == after.comparison.status == "disabled"


def test_an_outcome_bound_to_a_1_0_snapshot_compares_with_current_ones_by_criterion_id():
    """History graded before format 2.0 keeps its snapshot; it is verified as stored, then read as 2.0."""
    v1 = {"schema_version": "1.0", "templates": ["static_analysis"], "languages": ["python"],
          "criteria": {"base": {"weight": 100, "subjects": [
              {"subject_name": "Imports", "weight": 1, "tests": [criterion("a")]}]},
              "bonus": {"weight": 10, "tests": [criterion("b", imports=["sys"])]}}}
    current = compile_definition(upgrade_v1(v1).definition)
    stored = build_outcome(current, {"a": 0, "b": 100}).model_dump(mode="json")
    stored["provenance"] = {"schema_version": "1.0", "definition_hash": snapshot_hash(v1)}
    head = build_outcome(current, {"a": 100, "b": 100})
    result = compare_outcomes(stored, head, v1, current)
    assert result.compatibility == "cross_revision" and result.changed_definition_sections == ("schema_version",)
    assert {row.criterion_id: (row.status, row.delta) for row in result.criteria} == {
        "a": ("improved", 100), "b": ("unchanged", 0)}
    tampered = deepcopy(v1)
    tampered["criteria"]["bonus"]["weight"] = 20
    unbound = {**stored, "provenance": {**stored["provenance"], "schema_version": "2.0"}}
    for definition, outcome in ((tampered, stored), (v1, unbound)):
        with pytest.raises(ComparisonError) as failure:
            compare_outcomes(outcome, head, definition, current)
        assert (failure.value.code, failure.value.side) == ("DEFINITION_MISMATCH", "baseline")
