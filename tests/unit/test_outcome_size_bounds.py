"""Student-controlled text cannot size a terminal outcome (COR-06).

Reports and feedback are excerpted in one place to fixed UTF-8 bounds, scores are
unaffected, attested text above a bound is rejected rather than truncated, and
every valid definition's worst-case attestation fits the hosts' request limit.
"""
import json
import random
import re

import pytest
from pydantic import ValidationError

from autograder import (
    EvaluationInput, Submission, SubmissionFile, Template, TestFunction, TestResult, build_pipeline,
    compile_definition, compile_snapshot,
)
from autograder.models.contracts.definition import DefinitionValidationError
from autograder.models.contracts.outcome import (
    JSON_EXPANSION, MAX_FEEDBACK_BYTES, MAX_REPORT_BYTES, CompletedOutcome, FeedbackOutcome, TestOutcome,
    bound_text, validate_outcome, wire_bytes,
)
from autograder.models.contracts.verification import (
    MAX_ATTESTATION_BYTES, OutcomeTooLargeError, verify_outcome_size,
)
from autograder.services.grading import grade
from github_action.cloud_exporter import CloudPublisher
from submission_contract import MAX_METADATA_BYTES, MAX_REQUEST_BYTES

MARKER = re.compile(r"\n\[\.\.\. (\d+) of (\d+) bytes omitted \.\.\.\]\n")


# ---------------------------------------------------------------- excerpts

ALPHABET = ["a", "Z", " ", "\n", "\r\n", "\t", "\x00", "\x01", "\x7f", "é", "ß", "€", "中", "𝄞", "😀",
            "́", "\ud800", "\udfff", "\\", '"']


def random_text(rng, size):
    return "".join(rng.choice(ALPHABET) for _ in range(size))


def test_excerpts_are_deterministic_utf8_safe_and_never_exceed_the_bound():
    """Property test over a fixed seed: no wall-clock or ordering dependence."""
    rng = random.Random(420)
    for _ in range(3000):
        limit = rng.choice([64, 65, 100, 257, 1024, MAX_REPORT_BYTES])
        text = random_text(rng, rng.choice([0, 1, limit // 4, limit, limit * 2, limit * 10]))
        excerpt = bound_text(text, limit)
        assert excerpt == bound_text(text, limit)
        encoded = excerpt.encode("utf-8")  # strict: no lone surrogates survive an excerpt
        assert len(encoded) <= limit
        clean = text.encode("utf-8", "surrogatepass").decode("utf-8", "replace")
        if len(clean.encode("utf-8")) <= limit:
            assert excerpt == clean
            continue
        match = MARKER.search(excerpt)
        assert match, excerpt
        omitted, total = int(match.group(1)), int(match.group(2))
        assert total == len(clean.encode("utf-8"))
        head, tail = excerpt[:match.start()], excerpt[match.end():]
        assert clean.startswith(head) and clean.endswith(tail)
        assert omitted == total - len(head.encode("utf-8")) - len(tail.encode("utf-8")) > 0


def test_excerpt_keeps_head_and_tail_with_full_byte_count():
    text = "Expected: 5\nActual: " + "x" * 2_000_000 + "\nTraceback end"
    excerpt = bound_text(text, MAX_REPORT_BYTES)
    assert excerpt.startswith("Expected: 5\nActual: xxx")
    assert excerpt.endswith("xxx\nTraceback end")
    assert f"of {len(text)} bytes omitted" in excerpt
    assert len(excerpt.encode("utf-8")) <= MAX_REPORT_BYTES


def test_multibyte_text_is_cut_on_character_boundaries():
    text = "€" * MAX_REPORT_BYTES  # 3 bytes each
    excerpt = bound_text(text, MAX_REPORT_BYTES)
    head, tail = MARKER.split(excerpt)[0], MARKER.split(excerpt)[-1]
    assert set(head) == set(tail) == {"€"}
    assert len(excerpt.encode("utf-8")) <= MAX_REPORT_BYTES


# ---------------------------------------------------------------- contract validation

def leaf(report):
    return {"id": "a", "evaluator": "check", "name": "A", "score": 0.0, "weight": 100.0, "report": report}


@pytest.mark.parametrize("report", ["x" * MAX_REPORT_BYTES, "€" * (MAX_REPORT_BYTES // 3)])
def test_report_at_the_bound_is_valid(report):
    assert TestOutcome.model_validate(leaf(report)).report == report


@pytest.mark.parametrize("report", ["x" * (MAX_REPORT_BYTES + 1), "€" * (MAX_REPORT_BYTES // 3 + 1)])
def test_attested_report_above_the_bound_is_a_typed_error_not_a_truncation(report):
    with pytest.raises(ValidationError) as caught:
        TestOutcome.model_validate(leaf(report))
    [error] = caught.value.errors()
    assert error["type"] == "text_too_large" and error["loc"] == ("report",)


def test_attested_feedback_above_the_bound_is_a_typed_error():
    FeedbackOutcome(status="completed", content="x" * MAX_FEEDBACK_BYTES)
    with pytest.raises(ValidationError) as caught:
        FeedbackOutcome(status="completed", content="x" * (MAX_FEEDBACK_BYTES + 1))
    assert caught.value.errors()[0]["type"] == "text_too_large"


# ---------------------------------------------------------------- local enforcement

PREFIX = "Expected: ok\nActual: "


class Flood(TestFunction):
    """An evaluator echoing a student-sized report, as I/O evaluators do."""
    name = "flood"
    description = "Returns a report of the configured size."

    def execute(self, evaluation: EvaluationInput, *, size: int, score: float) -> TestResult:
        return TestResult(self.name, score, "Expected: ok\nActual: " + "\x01é" * size + "\nend")


class Local(Template):
    template_name = "Local"
    template_description = "Flooding reports."
    requires_sandbox = False

    def __init__(self):
        self.tests = {"flood": Flood()}


def flood_definition(count, size=1_000_000, feedback=False, score=0.0):
    return {"schema_version": "1.0", "templates": ["local"], "languages": ["python"],
            "criteria": {"base": {"weight": 100, "tests": [
                {"id": f"c{index}", "type": "flood", "name": f"Criterion {index}",
                 "parameters": {"size": size, "score": score}} for index in range(count)]}},
            "feedback": {"enabled": feedback, "preferences": {"general": {"show_passed_tests": True}}}}


def run(definition):
    pipeline = build_pipeline(definition=definition, templates={"local": Local()})
    outcome = pipeline.run(Submission("u", "u", "a", {"main.py": SubmissionFile("main.py", "")})).outcome
    assert outcome.status == "completed", outcome.error
    return pipeline, outcome


@pytest.mark.parametrize("score", [0.0, 37.5, 100.0])
def test_every_local_report_is_excerpted_once_and_the_score_is_unchanged(score):
    _, small = run(flood_definition(4, size=10, score=score))
    pipeline, outcome = run(flood_definition(4, score=score))
    assert outcome.score == small.score == score
    for test in outcome.tree.base.tests:
        assert test.score == score
        assert len(test.report.encode("utf-8")) <= MAX_REPORT_BYTES
        assert test.report.startswith("Expected: ok\nActual: \x01é")
        assert test.report.endswith("\x01é\nend")
        assert f"of {len(PREFIX) + 3_000_000 + 4} bytes omitted" in test.report
    assert [test.report for test in small.tree.base.tests] == ["Expected: ok\nActual: " + "\x01é" * 10 + "\nend"] * 4
    size = wire_bytes(outcome.model_dump(mode="json"))
    assert size <= pipeline.compiled.max_outcome_bytes
    assert size < 4 * JSON_EXPANSION * MAX_REPORT_BYTES + 16 * 1024
    verify_outcome_size(pipeline.compiled.max_outcome_bytes, outcome)
    assert validate_outcome(outcome.model_dump(mode="json")) == outcome


def test_feedback_repeating_flooded_reports_is_excerpted_and_keeps_the_final_score():
    _, outcome = run(flood_definition(60, size=10_000, feedback=True))
    content = outcome.feedback.content
    assert outcome.feedback.status == "completed"
    assert len(content.encode("utf-8")) <= MAX_FEEDBACK_BYTES
    assert MARKER.search(content)
    assert content.rstrip().endswith("0.00 / 100**")


# ---------------------------------------------------------------- definition budget

def sized_definition(count, padding=0):
    """Canonical as written, so it is also a valid stored snapshot."""
    tests = [{"id": f"t{index}", "type": "expect_output", "name": f"T{index}", "weight": 1,
              "parameters": {"inputs": [], "expected_output": "5", "program_command": "python3 main.py",
                             "normalization": True}}
             for index in range(count)]
    tests[0]["parameters"]["expected_output"] = "\x01" * padding
    return {"schema_version": "1.0", "templates": ["input_output"], "languages": ["python"],
            "criteria": {"base": {"weight": 100, "tests": tests}}}


def largest(build, upper):
    """The largest valid argument of ``build`` (compilation is monotonic in it)."""
    low, high = 0, upper
    while low < high:
        middle = (low + high + 1) // 2
        try:
            compile_definition(build(middle))
            low = middle
        except DefinitionValidationError:
            high = middle - 1
    return low


def test_compilation_rejects_a_definition_whose_worst_case_attestation_cannot_fit():
    count = largest(sized_definition, 5000)
    assert 400 < count < 5000
    compiled = compile_definition(sized_definition(count))
    assert wire_bytes(compiled.definition.model_dump(mode="json")) + compiled.max_outcome_bytes \
        <= MAX_ATTESTATION_BYTES
    assert compile_snapshot(compiled.definition.model_dump(mode="json")).max_outcome_bytes \
        == compiled.max_outcome_bytes
    for function in (compile_definition, compile_snapshot):
        with pytest.raises(DefinitionValidationError) as caught:
            function(sized_definition(count + 1))
        assert caught.value.errors() == [{"code": "DEFINITION_TOO_LARGE", "path": [], "message": caught.value.errors()[0]["message"]}]


def test_definition_authored_text_counts_against_the_same_budget():
    padding = largest(lambda size: sized_definition(1, size), 8 * 1024 * 1024)
    assert padding > 1024 * 1024
    with pytest.raises(DefinitionValidationError) as caught:
        compile_definition(sized_definition(1, padding + 1))
    assert caught.value.errors()[0]["code"] == "DEFINITION_TOO_LARGE"


def worst_outcome(compiled, reference="1"):
    """An outcome of ``compiled`` with every report and the feedback at their bound,
    using the characters with the largest JSON escaping."""
    report = "\x01" * MAX_REPORT_BYTES
    tree = grade(compiled.criteria_tree, {test.criterion_id: TestResult("", 33.333, report)
                                          for test in compiled.criteria_tree.get_all_tests()})
    return CompletedOutcome(
        schema_version="1.0", status="completed", execution_id="00000000-0000-4000-8000-000000000000",
        language="python", provenance={"definition_hash": compiled.definition_hash, "reference": reference,
                                       "revision": 1},
        started_at="2026-11-04T12:00:00Z", finished_at="2026-11-04T12:00:01Z", duration_ms=1000,
        score=tree.score, tree=tree, feedback={"status": "completed", "content": "\x01" * MAX_FEEDBACK_BYTES})


def test_worst_case_outcome_is_within_its_documented_bound():
    for count in (1, 10, 100):
        compiled = compile_definition(sized_definition(count))
        outcome = worst_outcome(compiled)
        assert outcome.tree.base.tests[0].report == "\x01" * MAX_REPORT_BYTES
        verify_outcome_size(compiled.max_outcome_bytes, outcome)
        # The bound is a function of criteria count, not loose by orders of magnitude.
        assert wire_bytes(outcome.model_dump(mode="json")) > 0.9 * compiled.max_outcome_bytes


def test_attested_outcome_above_its_definition_bound_is_rejected():
    compiled = compile_definition(sized_definition(2))
    data = worst_outcome(compiled).model_dump(mode="json")
    data["tree"]["base"]["tests"][0]["metadata"] = {"stuffing": "x" * compiled.max_outcome_bytes}
    with pytest.raises(OutcomeTooLargeError):
        verify_outcome_size(compiled.max_outcome_bytes, validate_outcome(data))


class Identity:
    submitter_id = "s" * 255
    submitter_name = "😀" * 255
    source = "github"


class Provenance:
    @staticmethod
    def metadata():
        return {"run": "\x01" * (MAX_METADATA_BYTES // 6 - 16)}


def test_the_largest_action_attestation_fits_the_host_request_limit():
    """The Action posts ``json.dumps(payload)``: the encoding ``wire_bytes`` measures."""
    count = largest(sized_definition, 5000)
    compiled = compile_definition(sized_definition(count))
    payload = CloudPublisher(None, 1, compiled.definition).payload(worst_outcome(compiled), Identity, Provenance)
    size = len(json.dumps(payload).encode("utf-8"))
    assert 0.95 * MAX_ATTESTATION_BYTES < size <= MAX_REQUEST_BYTES
    assert MAX_REQUEST_BYTES - MAX_ATTESTATION_BYTES >= size - (
        wire_bytes(payload["definition_snapshot"]) + wire_bytes(payload["outcome"]))
