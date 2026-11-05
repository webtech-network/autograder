"""The capacity benchmark's workloads are valid v1 definitions and its gates ignore timing.

The real HTTP/PostgreSQL/Docker path is tests/integration/test_capacity_benchmark.py.
"""
import pytest

from autograder import build_pipeline, compile_definition
from autograder.models.dataclass.submission import Submission, SubmissionFile
from autograder.models.language import Language
from scripts import capacity_benchmark as bench


@pytest.mark.parametrize("count", [1, 5, 31])
def test_workload_definitions_compile_with_the_requested_size(count):
    for definition in (bench.python_io_definition(count), bench.webdev_definition(count)):
        compiled = compile_definition(definition)
        tests = compiled.definition.criteria.base.tests
        assert len(tests) == count
        assert len({test.id for test in tests}) == count


def test_python_io_cases_are_distinct_and_match_the_submitted_program():
    tests = bench.python_io_definition(3)["criteria"]["base"]["tests"]
    assert [(test["parameters"]["inputs"], test["parameters"]["expected_output"]) for test in tests] == [
        (["0", "20"], "20"), (["1", "20"], "21"), (["2", "20"], "22")]
    program = bench.python_io_files("nonce")[0]["content"]
    assert "nonce" in program and "print(a + b)" in program


def test_webdev_pages_are_sized_unique_and_score_full_marks_offline():
    first, second = (bench.webdev_files(nonce, 20)[0] for nonce in ("run-0", "run-1"))
    assert first["content"] != second["content"]
    assert 20 * 1024 <= len(first["content"]) < 21 * 1024
    pipeline = build_pipeline(definition=compile_definition(bench.webdev_definition(30)))
    outcome = pipeline.run(Submission("benchmark", "user", "assignment",
                                      {"index.html": SubmissionFile("index.html", first["content"])},
                                      language=Language.NODE)).outcome
    assert outcome.status == "completed" and outcome.score == 100


def test_mix_alternates_configurations():
    args = bench.parse_args(["--token", "t", "--workload", "mix", "--submissions", "4"])
    definitions, submissions = bench.plan(args)
    assert set(definitions) == set(bench.ALIASES.values())
    assert [alias for alias, _ in submissions("run")] == [bench.ALIASES["python-io"], bench.ALIASES["webdev"]] * 2
    assert args.executions == 12


def test_percentiles_use_nearest_rank():
    summary = bench.percentiles([float(value) for value in range(1, 101)])
    assert summary == {"count": 100, "min": 1.0, "p50": 50.0, "p95": 95.0, "p99": 99.0, "max": 100.0}
    assert bench.percentiles([0.25]) == {"count": 1, "min": 0.25, "p50": 0.25, "p95": 0.25, "p99": 0.25,
                                         "max": 0.25}
    assert bench.percentiles([]) is None


def run(**overrides):
    base = {"acceptance": {"requested": 10, "accepted": 10, "status_codes": {"202": 10}},
            "drain": {"non_terminal": 0, "seconds": 9999.0},
            "outcomes": {"failure_codes": {}}, "executions": None}
    return base | overrides


def test_gates_pass_slow_runs_and_allowed_codes():
    assert bench.problems(run(), set()) == []
    allowed = run(outcomes={"failure_codes": {"CAPABILITY_UNAVAILABLE": 3}})
    assert bench.problems(allowed, {"CAPABILITY_UNAVAILABLE"}) == []
    saturated = run(executions={"status_codes": {"200": 2, "503": 9, "429": 1}})
    assert bench.problems(saturated, set()) == []


def test_gates_fail_rejection_non_terminal_unexpected_codes_and_execution_errors():
    found = bench.problems(run(acceptance={"requested": 10, "accepted": 8, "status_codes": {"202": 8, "500": 2}},
                               drain={"non_terminal": 1},
                               outcomes={"failure_codes": {"SANDBOX_ERROR": 1, "CAPABILITY_UNAVAILABLE": 2}},
                               executions={"status_codes": {"200": 1, "500": 1, "ReadTimeout": 1}}),
                           {"CAPABILITY_UNAVAILABLE"})
    assert found == ["2 submission(s) not accepted: {'202': 8, '500': 2}",
                     "1 accepted submission(s) did not reach a terminal state",
                     "unexpected failure codes: {'SANDBOX_ERROR': 1}",
                     "unexpected deliberate execution statuses: {'500': 1, 'ReadTimeout': 1}"]


def test_variance_reports_min_median_max_of_present_metrics():
    runs = [{"drain": {"seconds": value, "gradings_per_minute": None}, "sandboxes": {"unavailable": "x"}}
            for value in (3.0, 1.0, 2.0)]
    assert bench.variance(runs) == {"drain_seconds": {"min": 1.0, "median": 2.0, "max": 3.0}}


def test_token_is_required(monkeypatch):
    monkeypatch.delenv("AUTOGRADER_INTEGRATION_TOKEN", raising=False)
    with pytest.raises(SystemExit):
        bench.parse_args([])
