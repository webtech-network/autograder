"""ARC-02: one normalization, one immutable plan, isolated executions.

The snapshot, its hash, the executed evaluator inputs and the reported
parameters must all describe the same grading operation.
"""
from dataclasses import FrozenInstanceError
from unittest.mock import patch

import pytest
from pydantic import BaseModel, ConfigDict, Field, field_validator

from autograder import (
    CompiledDefinition, DefinitionValidationError, Submission, SubmissionFile, Template,
    TestFunction, TestResult, build_pipeline, compile_definition, compile_snapshot,
    evaluate_submission,
)


class LabelParameters(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    label: str
    items: list[str] = Field(default_factory=list)
    nested: dict[str, list[int]] = Field(default_factory=dict)

    @field_validator("label")
    @classmethod
    def exclaim(cls, value):
        # Deliberately non-idempotent: applying it twice is observable.
        return value + "!"


class RecordingLabel(TestFunction):
    """Records what it executes and then mutates every mutable input it got."""
    name = "label"
    description = "Record the executed label."
    config_schema = LabelParameters

    def __init__(self):
        self.executed = []

    def execute(self, evaluation, *, label, items, nested):
        self.executed.append({"label": label, "items": list(items), "nested": {k: list(v) for k, v in nested.items()}})
        items.append("mutated")
        nested.setdefault("a", []).append(99)
        nested["b"] = [1]
        return TestResult(self.name, 100, label)


class LabelTemplate(Template):
    template_name = "Label"
    template_description = "Trusted non-idempotent normalizer."
    requires_sandbox = False

    def __init__(self):
        self.tests = {"label": RecordingLabel()}



def raw_definition():
    return {"schema_version": "1.0", "templates": ["label"], "languages": ["python"],
            "criteria": {"base": {"weight": 100, "tests": [{
                "id": "labelled", "type": "label", "name": "Label",
                "parameters": {"label": "x", "items": ["one"], "nested": {"a": [1]}}}]}}}


def submission():
    return Submission("u", "u", "a", {"main.py": SubmissionFile("main.py", "print(1)")})


EXPECTED = {"label": "x!", "items": ["one"], "nested": {"a": [1]}}


def outcome_parameters(outcome):
    return outcome.model_dump(mode="json")["tree"]["base"]["tests"][0]["parameters"]


def test_non_idempotent_normalizer_snapshot_executed_and_reported_values_match():
    template = LabelTemplate()
    compiled = compile_definition(raw_definition(), templates={"label": template})
    snapshot = compiled.definition.model_dump(mode="json")
    assert snapshot["criteria"]["base"]["tests"][0]["parameters"] == EXPECTED
    assert compiled.criteria_tree.base.tests[0].parameters["label"] == "x!"

    outcome = evaluate_submission(submission(), definition=compiled)

    assert outcome.status == "completed"
    assert template.tests["label"].executed == [EXPECTED]
    assert outcome_parameters(outcome) == EXPECTED
    assert outcome.provenance.definition_hash == compiled.definition_hash


def test_raw_facade_input_is_normalized_exactly_once():
    template = LabelTemplate()
    outcome = evaluate_submission(submission(), definition=raw_definition(), templates={"label": template})
    assert template.tests["label"].executed == [EXPECTED]
    assert outcome_parameters(outcome) == EXPECTED


def test_reusing_a_compiled_definition_never_normalizes_again():
    template = LabelTemplate()
    compiled = compile_definition(raw_definition(), templates={"label": template})
    assert compile_definition(compiled) is compiled
    assert build_pipeline(definition=compiled).compiled is compiled
    # New templates revalidate the canonical snapshot without re-normalizing it.
    rebound = compile_definition(compiled, templates={"label": LabelTemplate()})
    assert rebound.definition_hash == compiled.definition_hash
    assert rebound.definition.model_dump(mode="json") == compiled.definition.model_dump(mode="json")
    assert rebound.criteria_tree.base.tests[0].parameters["label"] == "x!"


def test_stored_snapshot_is_validated_without_applying_raw_normalization():
    template = LabelTemplate()
    compiled = compile_definition(raw_definition(), templates={"label": template})
    stored = compiled.definition.model_dump(mode="json")

    loaded = compile_snapshot(stored, templates={"label": template})

    assert loaded.definition_hash == compiled.definition_hash
    assert loaded.definition.model_dump(mode="json") == stored
    outcome = build_pipeline(definition=loaded).run(submission()).outcome
    assert template.tests["label"].executed == [EXPECTED]
    assert outcome_parameters(outcome) == EXPECTED
    # Treating a stored snapshot as raw authoring input is a different operation.
    assert compile_definition(stored, templates={"label": template}).definition_hash != compiled.definition_hash


def test_mutating_evaluator_cannot_affect_plan_snapshot_report_or_next_run():
    template = LabelTemplate()
    compiled = compile_definition(raw_definition(), templates={"label": template})
    before_hash = compiled.definition_hash
    pipeline = build_pipeline(definition=compiled)

    first = pipeline.run(submission()).outcome
    second = pipeline.run(submission()).outcome

    assert template.tests["label"].executed == [EXPECTED, EXPECTED]
    assert outcome_parameters(first) == outcome_parameters(second) == EXPECTED
    assert compiled.definition.model_dump(mode="json")["criteria"]["base"]["tests"][0]["parameters"] == EXPECTED
    assert compiled.definition_hash == before_hash
    assert compile_snapshot(compiled.definition.model_dump(mode="json"),
                            templates={"label": template}).definition_hash == before_hash


def test_compiled_plan_cannot_be_modified_through_caller_references():
    raw = raw_definition()
    compiled = compile_definition(raw, templates={"label": LabelTemplate()})
    raw["criteria"]["base"]["tests"][0]["parameters"]["items"].append("caller")

    exposed = compiled.definition
    exposed.criteria.base.tests[0].parameters["items"].append("caller")
    exposed.criteria.base.tests[0].parameters["label"] = "changed"

    node = compiled.criteria_tree.base.tests[0]
    with pytest.raises(TypeError):
        node.parameters["label"] = "changed"
    with pytest.raises(AttributeError):
        node.parameters["items"].append("changed")
    with pytest.raises(TypeError):
        node.parameters["nested"]["a"] = ()
    with pytest.raises(FrozenInstanceError):
        node.weight = 0
    with pytest.raises(FrozenInstanceError):
        compiled.criteria_tree.base.tests = ()
    with pytest.raises(AttributeError):
        compiled.criteria_tree = None
    with pytest.raises(AttributeError):
        compiled._snapshot = {}  # pylint: disable=protected-access
    assert compiled.definition.model_dump(mode="json")["criteria"]["base"]["tests"][0]["parameters"] == EXPECTED


def test_compiled_definitions_cannot_be_constructed_outside_the_compiler():
    with pytest.raises(TypeError):
        CompiledDefinition(definition=None, definition_hash="0" * 64, criteria_tree=None, templates=[])
    with pytest.raises(TypeError):
        compile_snapshot(compile_definition(raw_definition(), templates={"label": LabelTemplate()}))


def builtin_snapshot():
    return compile_definition({"schema_version": "1.0", "templates": ["input_output"], "languages": ["python", "java"],
        "criteria": {"base": {"weight": 100, "tests": [{"id": "io", "type": "expect_output", "name": "IO",
            "parameters": {"program_command": {"python": "python3 main.py", "java": "java Main"},
                           "expected_output": "ok"}}]}}}).definition.model_dump(mode="json")


@pytest.mark.parametrize("mutate,code", [
    (lambda params: params.update(inputs="not-a-list"), "INVALID_DEFINITION"),
    (lambda params: params.update(unknown=True), "INVALID_DEFINITION"),
    (lambda params: params.pop("normalization"), "NON_CANONICAL_PARAMETERS"),
    (lambda params: params["program_command"].pop("java"), "MISSING_LANGUAGE_COMMAND"),
])
def test_untrusted_snapshots_are_still_validated(mutate, code):
    snapshot = builtin_snapshot()
    mutate(snapshot["criteria"]["base"]["tests"][0]["parameters"])
    with pytest.raises(DefinitionValidationError) as failure:
        compile_snapshot(snapshot)
    assert failure.value.errors()[0]["code"] == code
    assert failure.value.errors()[0]["path"][:5] == ["criteria", "base", "tests", 0, "parameters"]


def test_snapshot_structure_and_registry_are_validated():
    snapshot = builtin_snapshot()
    snapshot["criteria"]["base"]["tests"][0]["type"] = "missing"
    with pytest.raises(DefinitionValidationError) as failure:
        compile_snapshot(snapshot)
    assert failure.value.errors()[0]["code"] == "UNKNOWN_EVALUATOR"
    snapshot = builtin_snapshot()
    snapshot["unexpected"] = True
    with pytest.raises(DefinitionValidationError):
        compile_snapshot(snapshot)


def test_snapshot_validation_is_pure_and_hash_stable():
    snapshot = builtin_snapshot()
    with patch("boto3.client", side_effect=AssertionError("provider")), \
            patch("docker.from_env", side_effect=AssertionError("docker")), \
            patch("sandbox_manager.manager.SandboxManager.acquire_sandbox", side_effect=AssertionError("sandbox")):
        loaded = compile_snapshot(snapshot)
    assert loaded.definition_hash == compile_definition(snapshot).definition_hash
    assert loaded.definition.model_dump(mode="json") == snapshot
