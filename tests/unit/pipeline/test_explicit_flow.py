"""Explicit grading data flow and resource/failure boundaries."""
from dataclasses import asdict
from unittest.mock import patch

import pytest

from autograder import build_pipeline, evaluate_submission
from autograder.models.capabilities import HostCapabilities
from autograder.models.contracts.outcome import CompletedOutcome, FailedOutcome, validate_outcome
from autograder.models.result_tree import RootResultNode
from sandbox_manager.models.sandbox_models import CommandResponse
import autograder.autograder as coordinator
from autograder.models.evaluation_error import EvaluationError
from tests.unit.pipeline.test_terminal_outcome import definition, submission
from tests.unit.pipeline.test_host_capabilities import session
from autograder.template_library.static_analysis import ForbiddenImportTest


def grade_payload(outcome):
    return outcome.model_dump(exclude={"execution_id", "started_at", "finished_at", "duration_ms"})


def io_definition():
    value = definition()
    value["templates"] = ["input_output"]
    value["criteria"]["base"]["tests"] = [{
        "id": "runs", "type": "dont_fail", "name": "Runs",
        "parameters": {"program_command": "python main.py"},
    }]
    return value


def test_diagnostics_do_not_supply_data_or_change_execution_order():
    orders = []
    outcomes = []
    for observer_kind in ("disabled", "collect", "discard", "raise"):
        owned = session()
        owned.run_commands.return_value = CommandResponse("ok", "", 0, 0)
        events = []

        def observe(event, events=events, observer_kind=observer_kind):
            events.append(event)
            if observer_kind == "discard":
                events.clear()
            if observer_kind == "raise":
                raise RuntimeError("observer failed")

        outcome = build_pipeline(definition=io_definition(), capabilities=HostCapabilities(
            execution=lambda language, owned=owned: owned)).run(
                submission(), observer=None if observer_kind == "disabled" else observe).outcome
        assert outcome.status == "completed"
        outcomes.append(grade_payload(outcome))
        orders.append([call[0] for call in owned.mock_calls])
        if observer_kind == "collect":
            assert events[-1].operation == "close_session"
            assert all(set(asdict(event)) == {"execution_id", "operation", "status", "error"} for event in events)
            assert all(event.execution_id == outcome.execution_id for event in events)
    assert all(item == outcomes[0] for item in outcomes)
    assert all(item == orders[0] for item in orders)


def test_extra_diagnostic_event_cannot_change_grade():
    original = coordinator._observe  # pylint: disable=protected-access
    events = []

    def with_extra(observer, execution_id, operation, error=None):
        original(observer, execution_id, "additional_observation")
        original(observer, execution_id, operation, error)

    pipeline = build_pipeline(definition=definition())
    expected = pipeline.run(submission()).outcome
    with patch.object(coordinator, "_observe", side_effect=with_extra):
        actual = pipeline.run(submission(), observer=events.append).outcome
    assert grade_payload(actual) == grade_payload(expected)
    assert any(event.operation == "additional_observation" for event in events)


@pytest.mark.parametrize("failure", [None, "prepare", "evaluate"])
def test_close_precedes_terminal_construction_on_all_owned_paths(failure):
    owned = session()
    value = definition(preparation={"languages": {"python": {
        "setup_commands": [{"name": "prepare", "command": "prepare"}]}}})
    if failure == "prepare":
        owned.run_command.side_effect = RuntimeError("secret")
    if failure == "evaluate":
        owned_error = EvaluationError("SANDBOX_ERROR", "Assessment unavailable.", "capability", True)
    else:
        owned_error = None

    def completed(**kwargs):
        owned.close.assert_called_once()
        return CompletedOutcome(**kwargs)

    def failed(**kwargs):
        owned.close.assert_called_once()
        return FailedOutcome(**kwargs)

    pipeline = build_pipeline(definition=value, capabilities=HostCapabilities(execution=lambda language: owned))
    with patch("autograder.autograder.CompletedOutcome", side_effect=completed), \
         patch("autograder.autograder.FailedOutcome", side_effect=failed), \
         patch("autograder.template_library.static_analysis.ForbiddenImportTest.execute",
               side_effect=owned_error, wraps=ForbiddenImportTest().execute):
        outcome = pipeline.run(submission()).outcome
    assert outcome.status == ("completed" if failure is None else "failed")
    if failure:
        assert outcome.tree is None and outcome.score is None
    validate_outcome(outcome.model_dump(mode="json"))


@pytest.mark.parametrize("required_failure", [False, True])
def test_cleanup_failure_is_observable_without_replacing_the_grade(required_failure, caplog):
    owned = session()
    owned.close.side_effect = RuntimeError("private cleanup details")
    if required_failure:
        owned.run_command.side_effect = RuntimeError("private preparation details")
    events = []
    value = definition(preparation={"languages": {"python": {
        "setup_commands": [{"name": "prepare", "command": "prepare"}]}}})
    outcome = evaluate_submission(submission(), definition=value,
        capabilities=HostCapabilities(execution=lambda language: owned), observer=events.append)
    assert outcome.status == ("failed" if required_failure else "completed")
    assert events[-1].operation == "close_session"
    assert events[-1].error.code == "CLEANUP_ERROR"
    assert events[-1].error.correlation_id == outcome.execution_id
    assert "private" not in str(events[-1])
    assert "Execution session cleanup failed" in caplog.text
    owned.close.assert_called_once()


def test_feedback_disabled_opens_no_optional_work():
    with patch("autograder.autograder.FocusService") as focus, \
         patch("autograder.autograder.ReporterService") as reporter:
        outcome = build_pipeline(definition=definition()).run(submission()).outcome
    focus.assert_not_called()
    reporter.assert_not_called()
    assert outcome.feedback.status == "disabled"
    assert outcome.status == "completed" and outcome.score == 0


@pytest.mark.parametrize("failure", ["focus", "reporter", "empty_content"])
def test_optional_feedback_failures_preserve_the_validated_grade(failure):
    pipeline = build_pipeline(definition=definition(feedback=True))
    target = "autograder.autograder.FocusService.find" if failure == "focus" else "autograder.autograder.ReporterService.generate_feedback"
    with patch(target, **({"return_value": None} if failure == "empty_content" else {"side_effect": RuntimeError("secret")})):
        outcome = pipeline.run(submission("print(1)")).outcome
    assert outcome.status == "completed" and outcome.score == 100
    assert outcome.feedback.status == "failed"
    assert "secret" not in outcome.model_dump_json()


def test_repeated_runs_do_not_retain_artifacts_or_rebuild_the_compiled_tree():
    pipeline = build_pipeline(definition=definition())
    with patch("autograder.services.criteria_tree_service.CriteriaTreeService.build_tree", side_effect=AssertionError("runtime compilation")):
        before = pipeline.run(submission()).outcome
        after = pipeline.run(submission("print(1)")).outcome
    assert before.score == 0 and after.score == 100
    assert before.execution_id != after.execution_id
    assert before.tree.base.tests[0].score == 0


def test_public_builder_rejects_exporter_configuration():
    with pytest.raises(TypeError):
        build_pipeline(definition=definition(), export_results=True)  # pylint: disable=unexpected-keyword-arg


def test_invalid_result_snapshot_fails_before_feedback_and_still_closes():
    """An invalid result tree cannot become a completed grade during finalization."""
    owned = session()
    value = definition(feedback=True, preparation={"languages": {"python": {
        "setup_commands": [{"name": "prepare", "command": "prepare"}]}}})
    pipeline = build_pipeline(definition=value, capabilities=HostCapabilities(execution=lambda language: owned))
    with patch.object(RootResultNode, "to_dict", return_value={"score": 100}), \
         patch("autograder.autograder.FocusService") as focus:
        outcome = pipeline.run(submission()).outcome
    assert outcome.error.code == "INVALID_EVALUATOR_RESULT"
    assert outcome.score is None and outcome.tree is None
    focus.assert_not_called()
    owned.close.assert_called_once()
