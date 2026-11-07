"""ONB-06 with real Docker: `python -m execution_host.check --submission` grades the
calculator example's reference and broken solutions in this machine's sandboxes.

The command runs as a subprocess, exactly as an author runs it. Each run's
sandboxes are identified by the owner-process label the sandbox manager writes
(``<boot_id>:<pid>:<start>``), so the tests see that the check created one sandbox
per reference and removed every one of them, whatever the grade.
"""
# pylint: disable=missing-function-docstring
import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

from autograder.models.language import Language
from sandbox_manager.ownership import LABEL_OWNER_PROCESS
from tests.sandbox_profiles import TEST_IMAGES

ROOT = Path(__file__).resolve().parents[2]
CALCULATOR = ROOT / "examples/assets/input_output"
DEFINITION = CALCULATOR / "criteria_examples/1_base_only_simple.json"


@pytest.fixture(scope="module", autouse=True)
def runtime_images():
    for language in (Language.PYTHON, Language.JAVA):
        found = subprocess.run(["docker", "image", "inspect", TEST_IMAGES[language]], capture_output=True, check=False)
        assert found.returncode == 0, f"{TEST_IMAGES[language]} is missing: run `make sandbox-build-all`"


def reference(tmp_path: Path, source: str, target: str) -> Path:
    """A submission directory holding one example source under the name the definition requires."""
    directory = tmp_path / Path(source).stem
    directory.mkdir()
    shutil.copy(CALCULATOR / "code_examples" / source, directory / target)
    return directory


def docker_json(*arguments) -> list:
    output = subprocess.run(["docker", *arguments], capture_output=True, text=True, check=True).stdout
    return [json.loads(line) for line in output.splitlines() if line.strip()]


class Check:
    """One run of the command; afterwards, the sandboxes its process created and those left."""

    def __init__(self, *arguments):
        since = str(int(time.time()) - 1)
        process = subprocess.Popen(  # pylint: disable=consider-using-with
            [sys.executable, "-m", "execution_host.check", *map(str, arguments)], cwd=ROOT,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.stdout, self.stderr = process.communicate(timeout=600)
        self.returncode = process.returncode
        owner = re.compile(rf"^[^:]*:{process.pid}:")
        events = docker_json("events", "--since", since, "--until", str(int(time.time()) + 1),
                             "--filter", "type=container", "--filter", "event=create", "--format", "{{json .}}")
        self.created = [event["Actor"]["ID"] for event in events
                        if owner.match(event["Actor"]["Attributes"].get(LABEL_OWNER_PROCESS, ""))]
        self.left = [container for container in self.created
                     if subprocess.run(["docker", "inspect", container], capture_output=True, check=False).returncode == 0]

    def __str__(self):
        return self.stdout + self.stderr


def test_the_reference_scores_100_and_the_broken_solution_is_graded_not_failed(tmp_path):
    good = reference(tmp_path, "python/simple_calculator.py", "calculator.py")
    broken = reference(tmp_path, "python/broken_calculator.py", "calculator.py")
    run = Check(DEFINITION, "--language", "python", "--submission", good, "--submission", broken)
    assert run.returncode == 0, run
    assert f"Reference {good} (python): completed, score 100.00/100" in run.stdout
    assert f"Reference {broken} (python): completed, score 0.00/100" in run.stdout
    # Each criterion with its score, and the broken solution's report says what went wrong.
    assert re.search(r"100\.00 +base-tests-0  expect_output", run.stdout)
    assert "Expected" in run.stdout.split(f"Reference {broken}", 1)[1]
    assert len(run.created) == 2 and run.left == [], run  # one sandbox per reference, none left


def test_min_score_makes_a_broken_solution_fail_the_check(tmp_path):
    broken = reference(tmp_path, "python/broken_calculator.py", "calculator.py")
    run = Check(DEFINITION, "--language", "python", "--submission", broken, "--min-score", "100")
    assert run.returncode == 1, run
    assert "below --min-score 100" in run.stdout
    assert run.left == []


def test_a_reference_that_does_not_compile_prints_the_compiler_output(tmp_path):
    """The example's Java source keeps its own class name, so `javac Calculator.java` rejects it:
    the check prints ONB-02's explanation and the compiler's output instead of a score."""
    wrong_name = reference(tmp_path, "java/SimpleCalculator.java", "Calculator.java")
    run = Check(DEFINITION, "--language", "java", "--submission", wrong_name)
    assert run.returncode == 1, run
    assert f"Reference {wrong_name} (java): failed: PREPARATION_FAILED" in run.stdout
    assert "class SimpleCalculator is public, should be declared in a file named SimpleCalculator.java" in run.stdout
    assert "Traceback" not in run.stderr
    assert len(run.created) == 1 and run.left == [], run


def test_an_unreadable_reference_stops_the_check_before_any_sandbox_exists(tmp_path):
    good = reference(tmp_path, "python/simple_calculator.py", "calculator.py")
    run = Check(DEFINITION, "--language", "python", "--submission", good, "--submission", tmp_path / "missing")
    assert run.returncode == 2, run
    assert "must be an existing readable directory" in run.stderr
    assert run.created == []
