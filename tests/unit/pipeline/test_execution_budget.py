"""One execution budget, derived from declared deadlines and refused before anything runs (COR-02)."""
# pylint: disable=missing-function-docstring
from unittest.mock import Mock

import pytest

from autograder import (
    BaseExecutionTest, EvaluationError, EvaluationInput, HostCapabilities, Submission, SubmissionFile, Template,
    TestFunction, TestResult, build_pipeline, compile_definition,
)
from autograder.models.capabilities import (
    PROCESS_ALLOWANCE_SECONDS, SESSION_ALLOWANCE_SECONDS, SETUP_TIMEOUT_SECONDS, ExecutionBudget, check_budget,
    requirements_for,
)
from autograder.models.abstract.execution_test import RUN_TIMEOUT_SECONDS
from autograder.models.execution import ProviderAssessment
from autograder.models.language import Language
from tests.process_results import exited


def io(test_id="run"):
    return {"id": test_id, "type": "dont_fail", "name": test_id, "parameters": {"program_command": "CMD"}}


def ai(test_id="sort"):
    return {"id": test_id, "type": "ai_sorting_algorithm", "name": test_id,
            "parameters": {"algorithm_name": "Merge Sort"}}


def static(test_id="tag"):
    return {"id": test_id, "type": "has_tag", "name": test_id, "file": "index.html", "parameters": {"tag": "main"}}


def definition(tests, *, languages=("python",), preparation=None):
    return {"schema_version": "1.0", "templates": ["input_output", "static_analysis", "webdev"],
            "languages": list(languages), "criteria": {"base": {"weight": 100, "tests": tests}},
            "preparation": preparation or {}}


def budget(value, language=Language.PYTHON):
    return requirements_for(compile_definition(value), language).budget


# ----- derivation ---------------------------------------------------------------------

def test_each_selected_execution_criterion_contributes_its_declared_deadline():
    assert budget(definition([io("a"), io("b"), io("c")])) == ExecutionBudget(3 * RUN_TIMEOUT_SECONDS, 3)


def test_setup_commands_of_the_bound_language_count_and_other_languages_do_not():
    value = definition([io()], languages=("python", "java"), preparation={"languages": {
        "python": {"setup_commands": [{"name": "a", "command": "true"}, {"name": "b", "command": "true"}]},
        "java": {"setup_commands": [{"name": "compile", "command": "javac Main.java"}]}}})
    assert budget(value, Language.PYTHON) == ExecutionBudget(RUN_TIMEOUT_SECONDS + 2 * SETUP_TIMEOUT_SECONDS, 3)
    assert budget(value, Language.JAVA) == ExecutionBudget(RUN_TIMEOUT_SECONDS + SETUP_TIMEOUT_SECONDS, 2)


def test_static_definitions_have_an_empty_budget():
    assert budget(definition([static()])) == ExecutionBudget()


def test_ai_criteria_share_one_provider_call_and_run_no_process():
    assert budget(definition([ai("one"), ai("two")])) == ExecutionBudget(0.0, 0, 1)
    assert budget(definition([ai(), io()])) == ExecutionBudget(RUN_TIMEOUT_SECONDS, 1, 1)


def test_session_seconds_adds_one_allowance_per_process_and_one_per_session():
    assert ExecutionBudget(90.0, 3).session_seconds == 90 + 3 * PROCESS_ALLOWANCE_SECONDS + SESSION_ALLOWANCE_SECONDS


def test_check_budget_refuses_only_a_longer_session_than_the_host_grants():
    check_budget(ExecutionBudget(30.0, 1), None)
    check_budget(ExecutionBudget(30.0, 1), ExecutionBudget(30.0, 1).session_seconds)
    with pytest.raises(EvaluationError) as raised:
        check_budget(ExecutionBudget(30.0, 1), ExecutionBudget(30.0, 1).session_seconds - 1)
    assert (raised.value.code, raised.value.category, raised.value.retryable) == (
        "EXECUTION_BUDGET_EXCEEDED", "capability", False)


# ----- the pipeline: refused before any session, granted otherwise --------------------

def submission():
    return Submission("s", "s", "a", {"main.py": SubmissionFile("main.py", "print(1)"),
                                      "index.html": SubmissionFile("index.html", "<main></main>")},
                      language=Language.PYTHON)


def test_a_budget_beyond_the_host_maximum_fails_before_acquiring():
    acquire = Mock(side_effect=AssertionError("must not acquire"))
    value = definition([io(f"run{index}") for index in range(5)])
    host = HostCapabilities(execution=acquire, max_session_seconds=120)
    outcome = build_pipeline(definition=value, capabilities=host).run(submission()).outcome
    assert outcome.status == "failed" and outcome.score is None
    assert (outcome.error.code, outcome.error.retryable) == ("EXECUTION_BUDGET_EXCEEDED", False)
    acquire.assert_not_called()


def test_a_static_definition_needs_no_execution_time():
    outcome = build_pipeline(definition=definition([static()]),
                             capabilities=HostCapabilities(max_session_seconds=1)).run(submission()).outcome
    assert outcome.status == "completed" and outcome.score == 100


def test_the_session_is_granted_the_derived_budget():
    owned = Mock()
    owned.run_process.return_value = exited("")
    acquire = Mock(return_value=owned)
    host = HostCapabilities(execution=acquire, max_session_seconds=900)
    outcome = build_pipeline(definition=definition([io("a"), io("b")]), capabilities=host).run(submission()).outcome
    assert outcome.status == "completed"
    acquire.assert_called_once_with(Language.PYTHON, ExecutionBudget(2 * RUN_TIMEOUT_SECONDS, 2))


def test_a_host_refusing_the_budget_at_acquisition_is_not_a_transient_failure():
    refuse = Mock(side_effect=EvaluationError("EXECUTION_BUDGET_EXCEEDED", "refused", "capability"))
    outcome = build_pipeline(definition=definition([io()]),
                             capabilities=HostCapabilities(execution=refuse)).run(submission()).outcome
    assert (outcome.error.code, outcome.error.retryable) == ("EXECUTION_BUDGET_EXCEEDED", False)


def test_every_process_runs_before_the_provider_call():
    """The session's lifetime covers only process deadlines: the provider call comes last."""
    order = []
    owned = Mock()
    owned.run_process.side_effect = lambda request: order.append("process") or exited("")

    class Provider:
        deadline_seconds = 1.0

        def assess(self, requests, *, context_files, locale):  # pylint: disable=unused-argument
            order.append("provider")
            return [ProviderAssessment(request.criterion_id, 100) for request in requests]

    host = HostCapabilities(execution=lambda language, granted: owned, ai=Provider())
    value = definition([ai("first"), io("a"), ai("second"), io("b")])
    outcome = build_pipeline(definition=value, capabilities=host).run(submission()).outcome
    assert outcome.status == "completed", outcome.error
    assert order == ["process", "process", "provider"]
    assert [test.id for test in outcome.tree.base.tests] == ["first", "a", "second", "b"]


# ----- the declaration: execution evaluators state their process deadlines ------------

class Undeclared(TestFunction):
    name = "undeclared"
    description = "Runs processes without declaring their deadlines."
    required_capabilities = ("sandbox_execution",)

    def execute(self, evaluation: EvaluationInput) -> TestResult:
        return TestResult(self.name, 100, "")


class Declared(Undeclared):
    name = "declared"
    process_timeouts = (5, 10.5)


def custom(evaluator):
    return {"schema_version": "1.0", "templates": ["custom"], "languages": ["python"],
            "criteria": {"base": {"weight": 100, "tests": [
                {"id": "x", "type": evaluator.name, "name": "x", "parameters": {}}]}}}


def test_an_execution_evaluator_must_declare_its_process_deadlines():
    with pytest.raises(TypeError, match="process_timeouts"):
        Template("Custom", "", [Undeclared()]).validate_contract()
    compiled = compile_definition(custom(Declared()), templates={"custom": Template("Custom", "", [Declared()])})
    assert requirements_for(compiled, Language.PYTHON).budget == ExecutionBudget(15.5, 2)


@pytest.mark.parametrize("timeouts", [(0,), (601,), (True,), ("30",), [30]])
def test_process_deadlines_are_positive_and_within_the_process_contract(timeouts):
    evaluator = Declared()
    evaluator.process_timeouts = timeouts
    with pytest.raises(TypeError, match="process_timeouts"):
        Template("Custom", "", [evaluator]).validate_contract()


def test_the_public_execution_base_declares_its_one_run():
    assert BaseExecutionTest.process_timeouts == (RUN_TIMEOUT_SECONDS,)
