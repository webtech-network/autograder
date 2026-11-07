"""Real sandboxes receive each fixture's own bytes, including empty ones (#390).

The object store is an in-memory S3 stand-in; staging, permissions, setup and
grading run in an actual Docker sandbox composed by the shipped ``DockerHost``.
"""
# pylint: disable=missing-function-docstring
from dataclasses import replace

import pytest

from autograder import evaluate_submission
from autograder.models.dataclass.submission import Submission, SubmissionFile
from execution_host.docker import DockerHost
from autograder.models.language import Language
from tests.fake_object_store import fake_s3_provider
from tests.sandbox_profiles import sandbox_config

PROGRAM = """import os
root = '/tmp/app'
def read(name):
    with open(os.path.join(root, name), 'rb') as handle:
        return handle.read().decode()
def mode(name):
    return oct(os.stat(os.path.join(root, name)).st_mode & 0o777)
try:
    open(os.path.join(root, 'slash.txt'), 'a').close()
    guarded = 'writable'
except PermissionError:
    guarded = 'denied'
print(read('slash.txt'), read('nested/under.txt'), len(read('empty.txt')),
      mode('slash.txt'), mode('nested/under.txt'), guarded, sep='|')
"""

EXPECTED = "slash bytes|underscore bytes|0|0o444|0o644|denied"


def definition(fixtures):
    return {"schema_version": "2.0", "languages": ["python"],
            "criteria": {"base": {"tests": [{"id": "fixtures", "name": "Reads fixtures",
                "type": "expect_output", "parameters": {"program_command": "python main.py",
                                                        "inputs": [], "expected_output": EXPECTED}}]}},
            "preparation": {"languages": {"python": {"required_files": ["main.py"], "setup_commands": [
                {"name": "empty fixture present", "command": "sh -c 'test -f /tmp/app/empty.txt && test ! -s /tmp/app/empty.txt'"}]}},
                "fixtures": fixtures}}


FIXTURES = [{"reference": "course/a/b", "path": "slash.txt", "read_only": True},
            {"reference": "course/a_b", "path": "nested/under.txt", "read_only": False},
            {"reference": "course/empty", "path": "empty.txt", "read_only": True}]


@pytest.fixture(scope="module")
def host(tmp_path_factory):
    config = tmp_path_factory.mktemp("sandbox") / "sandbox.yml"
    config.write_text(sandbox_config())
    owner = DockerHost(mode="local", config_file=str(config))
    yield owner
    owner.close()


def grade(host, fixtures, objects):
    provider, store = fake_s3_provider(objects)
    submission = Submission("student", 1, 1, {"main.py": SubmissionFile("main.py", PROGRAM)},
                            language=Language.PYTHON)
    outcome = evaluate_submission(submission, definition=definition(fixtures),
                                  capabilities=replace(host.capabilities, fixtures=provider))
    return outcome, store


@pytest.mark.parametrize("order", [FIXTURES, FIXTURES[::-1]], ids=["slash-first", "underscore-first"])
def test_collision_prone_and_empty_fixtures_are_staged_and_graded(host, order):
    outcome, store = grade(host, order, {"course/a/b": b"slash bytes", "course/a_b": b"underscore bytes",
                                         "course/empty": b""})
    assert outcome.status == "completed", outcome.error
    assert outcome.score == 100
    assert [key for _, key in store.requests] == [fixture["reference"] for fixture in order]


def test_missing_fixture_fails_preparation_safely(host):
    outcome, _ = grade(host, FIXTURES, {"course/a/b": b"slash bytes", "course/empty": b""})
    assert outcome.status == "failed" and outcome.score is None and outcome.tree is None
    assert (outcome.error.code, outcome.error.retryable) == ("PREPARATION_ERROR", False)
