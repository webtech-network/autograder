"""Output-flooding programs in real sandbox containers cannot size the outcome (COR-06).

The 1 MiB per-stream process bound still applies to assessment; only the text
retained in the terminal outcome is excerpted.
"""
import json
import re

import pytest

from autograder import Submission, SubmissionFile, build_pipeline
from autograder.models.contracts.outcome import JSON_EXPANSION, MAX_REPORT_BYTES, validate_outcome, wire_bytes
from autograder.models.language import Language
from execution_host.docker import DockerHost
from tests.sandbox_profiles import sandbox_config

MIB = 1024 * 1024
MARKER = re.compile(r"\n\[\.\.\. (\d+) of (\d+) bytes omitted \.\.\.\]\n")

FLOOD = (
    "import sys\n"
    "sys.stdout.write('o' * 2_000_000)\n"
    "sys.stderr.write('e' * 2_000_000)\n"
    "open('out.txt', 'w').write('a' * 900_000)\n"
    "sys.exit(int(sys.stdin.readline() or 0))\n"
)


def criterion(identity, kind, **parameters):
    return {"id": identity, "type": kind, "name": identity,
            "parameters": {"program_command": "python3 main.py", **parameters}}


def definition(criteria):
    return {"schema_version": "1.0", "templates": ["input_output"], "languages": ["python"],
            "criteria": {"base": {"weight": 100, "tests": criteria}}}


@pytest.fixture(scope="module")
def docker_host(tmp_path_factory):
    config = tmp_path_factory.mktemp("sandbox") / "sandbox.yml"
    config.write_text(sandbox_config((Language.PYTHON,)))
    host = DockerHost(mode="local", config_file=str(config))
    yield host
    host.close()


def run(host, criteria):
    pipeline = build_pipeline(definition=definition(criteria), capabilities=host.capabilities)
    outcome = pipeline.run(Submission("student", "student", "flood", {"main.py": SubmissionFile("main.py", FLOOD)},
                                      language=Language.PYTHON)).outcome
    assert outcome.status == "completed", outcome.error
    return pipeline, outcome


def assert_bounded(pipeline, outcome, count):
    size = wire_bytes(outcome.model_dump(mode="json"))
    assert size <= pipeline.compiled.max_outcome_bytes
    assert size < count * JSON_EXPANSION * MAX_REPORT_BYTES + 32 * 1024
    assert len(json.dumps(outcome.model_dump(mode="json"), ensure_ascii=False)) < count * MAX_REPORT_BYTES + 32 * 1024
    assert validate_outcome(outcome.model_dump(mode="json")) == outcome


def excerpt_counts(report):
    match = MARKER.search(report)
    assert match, report[:200]
    assert len(report.encode("utf-8")) <= MAX_REPORT_BYTES
    return int(match.group(1)), int(match.group(2))


def test_issue_reproduction_four_flooded_expect_output_criteria(docker_host):
    """The issue's reproduction measured a 4.2 MB outcome, about 1 MiB per criterion."""
    pipeline, outcome = run(docker_host, [criterion(f"out-{index}", "expect_output", expected_output="5")
                                          for index in range(4)])
    assert outcome.score == 0
    assert_bounded(pipeline, outcome, 4)
    prefix = "FAILURE: Output Mismatch.\nExpected: '5'\nActual: 'ooo"
    for test in outcome.tree.base.tests:
        assert test.score == 0
        assert test.report.startswith(prefix) and test.report.endswith("ooo'")
        omitted, total = excerpt_counts(test.report)
        # Assessment still saw the full 1 MiB stream bound; the full size is reported.
        assert total == len(prefix) - 3 + MIB + 1 and omitted > total - MAX_REPORT_BYTES


def test_flooded_stderr_and_artifact_reports_are_bounded(docker_host):
    pipeline, outcome = run(docker_host, [
        criterion("crash", "dont_fail", user_input="1"),
        criterion("artifact", "expect_file_artifact", artifact_path="out.txt", expected_content="sum=5"),
        criterion("passes", "dont_fail"),
    ])
    crash, artifact, passes = outcome.tree.base.tests
    assert (crash.score, artifact.score, passes.score) == (0, 0, 100)
    assert outcome.score == pytest.approx(33.33)
    assert_bounded(pipeline, outcome, 3)
    assert crash.report.startswith("FAILURE: Your program crashed during execution.\nError:\neee")
    assert excerpt_counts(crash.report)[1] == len("FAILURE: Your program crashed during execution.\nError:\n") + MIB
    assert artifact.report.startswith("FAILURE: Content mismatch in artifact 'out.txt'.\nExpected:\nsum=5\nActual:\naaa")
    assert excerpt_counts(artifact.report)[1] > 900_000
    assert MARKER.search(passes.report) is None
