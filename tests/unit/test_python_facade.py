"""The documented extension runs offline through the supported facade."""
from copy import deepcopy
from unittest.mock import Mock

import pytest

from autograder import (
    compile_definition, describe_templates, evaluate_submission,
    DefinitionValidationError, Submission,
)
from examples.contracts.custom_evaluator import DEFINITION, TrustedTextTemplate, grade


def test_documented_custom_evaluator_and_catalog_need_no_external_capabilities(monkeypatch):
    def unavailable(*args, **kwargs):
        pytest.fail("Static compilation/discovery/evaluation must be offline")

    monkeypatch.setattr("socket.socket.connect", unavailable)
    monkeypatch.setattr("sandbox_manager.manager.get_sandbox_manager", unavailable)
    monkeypatch.setattr("execution_host.openai_provider.AiExecutor.__init__", unavailable)
    monkeypatch.setattr("execution_host.secrets.fetch_secret", unavailable)
    assert describe_templates().templates
    assert grade("<h1>Hello</h1>").score == 100
    missing = grade("<h1>Goodbye</h1>")
    assert missing.status == "completed" and missing.score == 0


def test_injected_template_contract_is_checked():
    template = TrustedTextTemplate()
    template.validate_contract = Mock(side_effect=ValueError("broken contract"))
    with pytest.raises(DefinitionValidationError) as error:
        compile_definition(DEFINITION, templates={"trusted_text": template})
    template.validate_contract.assert_called_once_with()
    assert error.value.errors()[0]["code"] == "INVALID_TEMPLATE"


def test_facade_returns_failed_outcome_for_execution_error():
    submission = Submission(username="local", user_id="local", assignment_id="local",
                            language="python", submission_files={})
    outcome = evaluate_submission(submission, definition=DEFINITION,
                                  templates={"trusted_text": TrustedTextTemplate()})
    assert outcome.status == "failed"
    assert outcome.score is None and outcome.tree is None
    assert outcome.error.code == "LANGUAGE_NOT_ALLOWED"


@pytest.mark.parametrize("templates", ["webdev", "webdev,static_analysis", [{"source": "pass"}]])
def test_definition_cannot_load_source_or_legacy_template_strings(templates):
    value = deepcopy(DEFINITION)
    value["templates"] = templates
    with pytest.raises(DefinitionValidationError):
        compile_definition(value)
