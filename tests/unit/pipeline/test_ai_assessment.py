"""AI criteria are assessed in one provider batch keyed by criterion ID (ARC-07).

The fake provider records every call. The previous implementation made exactly
one provider call per run for all selected AI criteria (and none without AI
criteria); these tests pin that call count while exercising the assessment
implementation that now owns batching and provider-output validation.
"""
import importlib
import inspect
import math
from unittest.mock import MagicMock

import pytest

from autograder import (
    AiTestFunction, EvaluationInput, HostCapabilities, ProviderAssessment, Submission, SubmissionFile,
    Template, TestFunction, TestResult, build_pipeline,
)
from autograder.models.criteria_tree import CategoryNode, CriteriaTree, TestNode
from autograder.models.evaluation_error import EvaluationError
from autograder.models.execution import AssessmentRequest
from autograder.services.assessment import assess_many, prepare_criteria
from autograder.services.grading import grade
from execution_host.openai_provider import AIResponseModel, AiExecutor, TestOutput
from tests.grading import FakeProvider


class Review(AiTestFunction):
    """One AI evaluator type, repeated by several criteria with different prompts."""
    name = "review"
    description = "AI review."

    def build_prompt(self, evaluation: EvaluationInput, *, focus: str) -> str:
        return f"Review {focus} in {', '.join(file.filename for file in evaluation.files)}"


class Mutating(AiTestFunction):
    name = "mutating"
    description = "Mutates its isolated parameter copy."

    def build_prompt(self, evaluation: EvaluationInput, *, items: list[str]) -> str:
        items.append("mutated")
        return f"Items {items}"


class Static(TestFunction):
    """An ordinary evaluator that records exactly what it receives."""
    name = "static"
    description = "Static check."

    def __init__(self):
        self.calls = []

    def execute(self, evaluation: EvaluationInput, *, value: int) -> TestResult:
        self.calls.append((evaluation, value))
        return TestResult(self.name, value, f"static {value}")


def template(*evaluators):
    class Local(Template):
        template_name = "Local"
        template_description = "Local evaluators."
        requires_sandbox = False

        def __init__(self):
            self.tests = {evaluator.name: evaluator for evaluator in evaluators}
    return Local()


def ai(criterion_id, focus, name="Review"):
    return {"id": criterion_id, "type": "review", "name": name, "parameters": {"focus": focus}}


def definition(*tests):
    return {"schema_version": "1.0", "templates": ["local"], "languages": ["python"],
            "criteria": {"base": {"weight": 100, "tests": list(tests)}}}


def run(provider, *tests, static=None):
    static = static or Static()
    pipeline = build_pipeline(definition=definition(*tests), templates={"local": template(Review(), Mutating(), static)},
                              capabilities=HostCapabilities(ai=provider))
    submission = Submission("u", "u", "a", {"main.py": SubmissionFile("main.py", "print(1)"),
                                             "README.md": SubmissionFile("README.md", "docs")})
    return pipeline.run(submission).outcome


def leaves(outcome):
    return {test.id: (test.name, test.evaluator, test.score, test.report) for test in outcome.tree.base.tests}


# --- Exact coverage, keyed by criterion ID -----------------------------------

def test_single_ai_criterion_is_a_one_item_batch():
    provider = FakeProvider(score=80)
    outcome = run(provider, ai("only", "naming"))
    assert outcome.status == "completed" and outcome.score == 80
    [(requests, context, locale)] = provider.calls
    assert requests == (AssessmentRequest("only", "Review naming in README.md, main.py"),)
    assert context == {"README.md": "docs", "main.py": "print(1)"} and locale == "en"
    assert leaves(outcome) == {"only": ("Review", "review", 80, "assessed only")}


def test_repeated_evaluator_types_and_duplicate_labels_stay_distinct_by_id():
    """Same evaluator, same display label (with slashes): results never collide."""
    scores = {"sorting-correctness": 90.0, "sorting-explanation": 40.0, "style:a": 10.0}
    provider = FakeProvider(lambda requests: [
        ProviderAssessment(request.criterion_id, scores[request.criterion_id], request.prompt)
        for request in reversed(requests)])  # answer order is irrelevant
    outcome = run(provider, ai("sorting-correctness", "correctness", "Sorting / review"),
                  ai("sorting-explanation", "explanation", "Sorting / review"),
                  ai("style:a", "style", "Sorting / review"))
    assert outcome.status == "completed"
    [(requests, _, _)] = provider.calls
    assert [request.criterion_id for request in requests] == list(scores)
    prompts = [f"Review {focus} in README.md, main.py" for focus in ("correctness", "explanation", "style")]
    assert [request.prompt for request in requests] == prompts
    assert leaves(outcome) == {
        criterion_id: ("Sorting / review", "review", scores[criterion_id], prompt)
        for criterion_id, prompt in zip(scores, prompts)
    }
    assert outcome.score == pytest.approx(140 / 3, abs=0.01)


@pytest.mark.parametrize("count", [0, 1, 2, 5])
def test_call_count_matches_previous_batching(count):
    """Previous behavior: one provider call per run for any number of AI criteria, none without."""
    provider = FakeProvider()
    tests = [ai(f"ai-{index}", f"focus {index}") for index in range(count)]
    tests.append({"id": "static", "type": "static", "name": "Static", "parameters": {"value": 100}})
    assert run(provider, *tests).status == "completed"
    assert len(provider.calls) == (1 if count else 0)
    assert sum(len(requests) for requests, _, _ in provider.calls) == count


def test_each_run_makes_its_own_single_call_without_caching():
    provider = FakeProvider()
    pipeline = build_pipeline(definition=definition(ai("a", "x"), ai("b", "y")), templates={"local": template(Review())},
                              capabilities=HostCapabilities(ai=provider))
    submission = Submission("u", "u", "a", {"main.py": SubmissionFile("main.py", "")})
    pipeline.run(submission)
    pipeline.run(submission)
    assert [len(requests) for requests, _, _ in provider.calls] == [2, 2]


def test_mixed_rubric_merges_ai_and_ordinary_results_before_aggregation():
    static = Static()
    provider = FakeProvider(score=50)
    outcome = run(provider, ai("ai", "naming"), {"id": "static", "type": "static", "name": "Static",
                                                   "parameters": {"value": 100}}, static=static)
    assert outcome.status == "completed" and outcome.score == 75
    assert leaves(outcome)["static"] == ("Static", "static", 100, "static 100")
    [(evaluation, value)] = static.calls
    # Ordinary evaluators receive only their typed input and parameters.
    assert value == 100 and set(vars(evaluation)) == {"files", "language", "locale", "session"}


def test_each_prompt_receives_an_isolated_parameter_copy():
    provider = FakeProvider()
    tests = [{"id": "m", "type": "mutating", "name": "M", "parameters": {"items": ["a"]}}]
    pipeline = build_pipeline(definition=definition(*tests), templates={"local": template(Mutating())},
                              capabilities=HostCapabilities(ai=provider))
    submission = Submission("u", "u", "a", {"main.py": SubmissionFile("main.py", "")})
    first = pipeline.run(submission).outcome
    pipeline.run(submission)
    assert [requests[0].prompt for requests, _, _ in provider.calls] == ["Items ['a', 'mutated']"] * 2
    assert first.tree.base.tests[0].parameters == {"items": ["a"]}


# --- Unknown, duplicate, missing and invalid output fail the required grade ---

def _answer_all(transform):
    return lambda requests: [transform(request) for request in requests]


INVALID = {
    "unknown": (lambda requests: [*(ProviderAssessment(r.criterion_id, 100) for r in requests),
                                  ProviderAssessment("unknown", 100)], "INVALID_EVALUATOR_RESULT"),
    "duplicate": (lambda requests: [*(ProviderAssessment(r.criterion_id, 100) for r in requests),
                                    ProviderAssessment(requests[0].criterion_id, 100)], "INVALID_EVALUATOR_RESULT"),
    "missing": (lambda requests: [ProviderAssessment(r.criterion_id, 100) for r in requests[1:]],
                "MISSING_EVALUATOR_RESULT"),
    "empty": (lambda requests: [], "MISSING_EVALUATOR_RESULT"),
    "score above range": (_answer_all(lambda r: ProviderAssessment(r.criterion_id, 101)), "INVALID_EVALUATOR_RESULT"),
    "negative score": (_answer_all(lambda r: ProviderAssessment(r.criterion_id, -1)), "INVALID_EVALUATOR_RESULT"),
    "nan score": (_answer_all(lambda r: ProviderAssessment(r.criterion_id, math.nan)), "INVALID_EVALUATOR_RESULT"),
    "infinite score": (_answer_all(lambda r: ProviderAssessment(r.criterion_id, math.inf)), "INVALID_EVALUATOR_RESULT"),
    "boolean score": (_answer_all(lambda r: ProviderAssessment(r.criterion_id, True)), "INVALID_EVALUATOR_RESULT"),
    "text score": (_answer_all(lambda r: ProviderAssessment(r.criterion_id, "90")), "INVALID_EVALUATOR_RESULT"),
    "missing score": (_answer_all(lambda r: ProviderAssessment(r.criterion_id, None)), "INVALID_EVALUATOR_RESULT"),
    "non-text report": (_answer_all(lambda r: ProviderAssessment(r.criterion_id, 50, None)), "INVALID_EVALUATOR_RESULT"),
    "foreign result type": (_answer_all(lambda r: TestResult(r.criterion_id, 50, "")), "INVALID_EVALUATOR_RESULT"),
    "legacy mapping": (lambda requests: {r.criterion_id: TestResult(r.criterion_id, 50, "") for r in requests},
                       "INVALID_EVALUATOR_RESULT"),
    "nothing": (lambda requests: None, "INVALID_EVALUATOR_RESULT"),
}


@pytest.mark.parametrize("count", [1, 3], ids=["single", "multiple"])
@pytest.mark.parametrize("case", sorted(INVALID))
def test_invalid_provider_output_fails_without_grade_or_retry(case, count):
    """Single- and multi-item batches share one validation and error mapping."""
    answer, code = INVALID[case]
    provider = FakeProvider(answer)
    tests = [ai(f"ai-{index}", "x") for index in range(count)]
    outcome = run(provider, *tests, {"id": "static", "type": "static", "name": "S", "parameters": {"value": 100}})
    assert outcome.status == "failed"
    assert outcome.score is None and outcome.tree is None
    assert (outcome.error.code, outcome.error.category, outcome.error.retryable) == (code, "provider", True)
    assert len(provider.calls) == 1


@pytest.mark.parametrize("count", [1, 3], ids=["single", "multiple"])
def test_provider_exceptions_map_to_one_safe_error(count):
    def broken(requests):
        raise RuntimeError("secret upstream detail")
    outcome = run(FakeProvider(broken), *[ai(f"ai-{index}", "x") for index in range(count)])
    assert outcome.status == "failed" and outcome.tree is None
    assert outcome.error.code == "PROVIDER_ERROR"
    assert "secret" not in outcome.error.message


def test_provider_evaluation_errors_pass_through_unchanged():
    def unavailable(requests):
        raise EvaluationError("PROVIDER_TIMEOUT", "The assessment provider timed out.", "provider", True)
    outcome = run(FakeProvider(unavailable), ai("a", "x"))
    assert (outcome.error.code, outcome.error.message) == ("PROVIDER_TIMEOUT", "The assessment provider timed out.")


def test_missing_provider_fails_before_assessment():
    static = Static()
    pipeline = build_pipeline(definition=definition(ai("a", "x"), {"id": "s", "type": "static", "name": "S",
                                                                      "parameters": {"value": 1}}),
                              templates={"local": template(Review(), static)})
    outcome = pipeline.run(Submission("u", "u", "a", {"main.py": SubmissionFile("main.py", "")})).outcome
    assert outcome.error.code == "PROVIDER_UNAVAILABLE" and static.calls == []


def test_assess_many_requires_a_provider_and_unique_ids():
    tree = CriteriaTree(base=CategoryNode("base", 100, tests=[
        TestNode("A", Review(), {"focus": "x"}, criterion_id="same"),
        TestNode("B", Review(), {"focus": "y"}, criterion_id="same")]))
    prepared = prepare_criteria(tree, Submission("u", "u", "a", {}))
    with pytest.raises(EvaluationError) as error:
        assess_many(prepared[:1], None, context_files={}, locale="en")
    assert error.value.code == "PROVIDER_UNAVAILABLE"
    provider = FakeProvider()
    with pytest.raises(EvaluationError) as error:
        assess_many(prepared, provider, context_files={}, locale="en")
    assert error.value.code == "INVALID_DEFINITION" and provider.calls == []


def test_ai_evaluators_are_never_executed_individually():
    with pytest.raises(EvaluationError, match="host-supplied"):
        Review().execute(EvaluationInput(), focus="x")


# --- No AI cache transport through generic layers -----------------------------

def test_generic_grader_has_no_ai_parameters_and_executes_no_evaluator():
    assert list(inspect.signature(grade).parameters) == ["criteria", "results"]
    function = MagicMock(spec=Static)
    function.name = "static"
    tree = CriteriaTree(base=CategoryNode("base", 100, tests=[TestNode("S", function, criterion_id="s")]))
    assert grade(tree, {"s": TestResult("static", 40, "r")}).score == 40
    function.execute.assert_not_called()
    with pytest.raises(EvaluationError) as error:
        grade(tree, {})
    assert error.value.code == "MISSING_EVALUATOR_RESULT"


@pytest.mark.parametrize("module", ["autograder.services.ai_batch", "autograder.utils.executors.ai_executor",
                                    "autograder.services.grader.grader_service"])
def test_global_batch_stage_and_untyped_inputs_are_removed(module):
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module(module)


# --- The OpenAI adapter translates structured output only ----------------------

def _executor(parsed=None, error=None):
    executor = AiExecutor.__new__(AiExecutor)  # skip credential lookup
    executor.model = "test-model"
    executor.client = MagicMock()
    if error:
        executor.client.responses.parse.side_effect = error
    else:
        executor.client.responses.parse.return_value.output_parsed = parsed
    return executor


def test_openai_adapter_sends_one_request_keyed_by_criterion_id():
    parsed = AIResponseModel(results=[TestOutput(criterion_id="b", feedback="fb", score=60.0),
                                      TestOutput(criterion_id="a", feedback="fa", score=80.0)])
    executor = _executor(parsed)
    answers = executor.assess([AssessmentRequest("a", "pa"), AssessmentRequest("b", "pb")],
                              context_files={"main.py": "x"}, locale="en")
    assert answers == [ProviderAssessment("b", 60.0, "fb"), ProviderAssessment("a", 80.0, "fa")]
    executor.client.responses.parse.assert_called_once()
    prompt = executor.client.responses.parse.call_args.kwargs["input"][1]["content"]
    assert '"criterion_id": "a"' in prompt and '"prompt": "pa"' in prompt and "main.py" in prompt
    assert "title" not in TestOutput.model_fields and "subject" not in TestOutput.model_fields


def test_openai_adapter_makes_no_call_for_an_empty_batch():
    executor = _executor()
    assert executor.assess([], context_files={}, locale="en") == []
    executor.client.responses.parse.assert_not_called()


@pytest.mark.parametrize("parsed,error,code", [
    (None, None, "MISSING_EVALUATOR_RESULT"),
    (None, RuntimeError("network"), "PROVIDER_ERROR"),
])
def test_openai_adapter_failures_are_safe_provider_errors(parsed, error, code):
    with pytest.raises(EvaluationError) as failure:
        _executor(parsed, error).assess([AssessmentRequest("a", "p")], context_files={}, locale="en")
    assert failure.value.code == code


def test_two_executors_share_no_module_state():
    import execution_host.openai_provider as module  # pylint: disable=import-outside-toplevel
    assert not hasattr(module, "ai_executor")
