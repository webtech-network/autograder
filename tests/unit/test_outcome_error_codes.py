"""Outcome error codes are one closed vocabulary, enumerated from the emitting code."""
import ast
import json
from pathlib import Path
import re

import pytest

from autograder.models.contracts import outcome as outcome_contract

ROOT = Path(__file__).resolve().parents[2]
ENGINE = ("autograder", "execution_host")
HOSTS = ("web", "github_action")


def _strings(node):
    """Constant string values, including both branches of a conditional expression."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return {node.value}
    if isinstance(node, ast.IfExp):
        return _strings(node.body) | _strings(node.orelse)
    return set()


def _argument(call, position, name):
    for keyword in call.keywords:
        if keyword.arg == name:
            return keyword.value
    return call.args[position] if len(call.args) > position else None


def emitted_codes(packages):
    """Every literal code a module can place into an outcome or diagnostic error."""
    codes = {}
    for package in packages:
        for path in (ROOT / package).rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                found = set()
                if isinstance(node, ast.Call):
                    callee = getattr(node.func, "id", getattr(node.func, "attr", None))
                    if callee == "EvaluationError":
                        found = _strings(_argument(node, 0, "code"))
                    elif callee == "OutcomeError":
                        found = _strings(_argument(node, 0, "code"))
                    elif callee == "failed_outcome":
                        found = _strings(_argument(node, 1, "code"))
                elif isinstance(node, ast.FunctionDef) and node.name == "failed_outcome":
                    names = [argument.arg for argument in node.args.args][-len(node.args.defaults):]
                    found = _strings(dict(zip(names, node.args.defaults)).get("code"))
                elif isinstance(node, ast.FunctionDef) and node.name == "select_language":
                    # The pipeline exposes these definition errors as submission outcome codes.
                    found = {value for call in ast.walk(node) if isinstance(call, ast.Call)
                             and getattr(call.func, "id", None) == "_error" for value in _strings(call.args[0])}
                elif isinstance(node, ast.Dict):
                    keys = {key.value for key in node.keys if isinstance(key, ast.Constant)}
                    if {"code", "correlation_id"} <= keys:  # an outcome-error-shaped literal
                        found = _strings(node.values[[getattr(k, "value", None) for k in node.keys].index("code")])
                for code in found:
                    codes.setdefault(code, set()).add(str(path.relative_to(ROOT)))
    return codes


def matrix_codes():
    text = (ROOT / "docs/contracts/OUTCOMES.md").read_text(encoding="utf-8")
    rows = [line for line in text.splitlines() if line.startswith("|")]
    return set(re.findall(r"`([A-Z][A-Z0-9_]+)`", "\n".join(rows)))


def test_one_unexpected_failure_code():
    emitted = emitted_codes(ENGINE + HOSTS)
    assert "EXECUTION_ERROR" in emitted
    assert "EXECUTION_FAILED" not in emitted
    assert {path.split("/")[0] for path in emitted["EXECUTION_ERROR"]} == {"autograder", "web"}


def test_every_emitted_code_is_published_and_every_published_code_is_emitted():
    engine, hosts = emitted_codes(ENGINE), emitted_codes(HOSTS)
    assert set(engine) == set(outcome_contract.ENGINE_ERROR_CODES)
    assert set(hosts) - set(engine) == set(outcome_contract.HOST_ERROR_CODES)
    assert set(outcome_contract.OUTCOME_ERROR_CODES) == set(engine) | set(hosts)


def test_outcomes_matrix_lists_exactly_the_vocabulary():
    assert matrix_codes() == set(outcome_contract.OUTCOME_ERROR_CODES)


@pytest.mark.parametrize("schema", [
    lambda: outcome_contract.outcome_json_schema()["$defs"]["OutcomeError"],
    lambda: json.loads((ROOT / "docs/contracts/v1/terminal-outcome.schema.json").read_text())["$defs"]["OutcomeError"],
    lambda: json.loads((ROOT / "docs/contracts/v1/openapi.json").read_text())["components"]["schemas"]["OutcomeError"],
])
def test_schemas_publish_the_closed_vocabulary(schema):
    assert schema()["properties"]["code"]["enum"] == list(outcome_contract.OUTCOME_ERROR_CODES)


@pytest.mark.parametrize("code", ["EXECUTION_FAILED", "CUSTOM_CODE", "execution_error", ""])
def test_unpublished_codes_are_rejected(code):
    from autograder.models.evaluation_error import EvaluationError
    with pytest.raises(ValueError):
        outcome_contract.OutcomeError(code=code, message="m", category="internal", retryable=False,
                                      correlation_id="c")
    with pytest.raises(ValueError):
        EvaluationError(code, "message")


@pytest.mark.parametrize("code", ["RECOVERY_EXHAUSTED", "LEGACY_UNVERIFIED"])
def test_host_only_codes_cannot_be_raised_by_evaluators(code):
    from autograder.models.evaluation_error import EvaluationError
    with pytest.raises(ValueError):
        EvaluationError(code, "message")


def test_an_unpublished_evaluator_code_is_the_one_unexpected_failure():
    """A trusted evaluator inventing a code cannot crash finalization or widen the vocabulary."""
    from unittest.mock import patch
    from autograder import build_pipeline
    from autograder.models.evaluation_error import EvaluationError
    from tests.unit.pipeline.test_terminal_outcome import definition, submission

    def invent(*args, **kwargs):
        raise EvaluationError("CUSTOM_TIMEOUT", "secret detail", "provider", True)

    with patch("autograder.autograder.assess_criteria", side_effect=invent):
        outcome = build_pipeline(definition=definition()).run(submission()).outcome
    assert outcome.status == "failed"
    assert (outcome.error.code, outcome.error.category) == ("EXECUTION_ERROR", "internal")
    assert "secret" not in outcome.model_dump_json()
