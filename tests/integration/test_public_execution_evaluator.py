"""An execution evaluator written only against ``autograder`` grades in a real sandbox (ONB-08).

``examples/contracts/execution_evaluator.py`` imports nothing but the public
package. Here it runs through the shipped Docker host instead of its fake
session: the same ``BaseExecutionTest`` helpers produce a pass, an assessed zero
for wrong output and an assessed zero for a crashing program.
"""
import pytest

from autograder import Submission, SubmissionFile, evaluate_submission
from execution_host.docker import DockerHost
from examples.contracts.execution_evaluator import DEFINITION, TEMPLATE
from tests.sandbox_profiles import sandbox_config
from autograder.models.language import Language


@pytest.fixture(scope="module")
def docker_host(tmp_path_factory):
    config = tmp_path_factory.mktemp("sandbox") / "sandbox.yml"
    config.write_text(sandbox_config(languages=(Language.PYTHON,)))
    host = DockerHost(mode="local", config_file=str(config))
    yield host
    host.close()


@pytest.mark.parametrize("program, score, report", [
    ("print('Hello, ' + input())", 100, "Expected line printed."),
    ("print('Bye, ' + input())", 0, "Expected line missing."),
    ("raise SystemExit('boom: ' + input())", 0, "boom: Ada"),
], ids=["passes", "wrong-output", "nonzero-exit"])
def test_public_surface_execution_evaluator_runs_in_a_real_sandbox(docker_host, program, score, report):
    outcome = evaluate_submission(
        Submission("student", "student", "public-surface", {"main.py": SubmissionFile("main.py", program)}),
        definition=DEFINITION, templates={"program_checks": TEMPLATE}, capabilities=docker_host.capabilities)
    assert outcome.status == "completed", outcome.error
    [test] = outcome.tree.base.tests
    assert (test.evaluator, test.score) == ("prints_line", score)
    assert report in test.report
