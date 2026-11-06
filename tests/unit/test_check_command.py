"""ONB-06: `python -m execution_host.check` as an author or a course repository's CI runs it.

Every test runs the command in a subprocess and asserts its output and exit
status: 0 valid (and every reference graded, at or above --min-score), 1 a
problem in the definition or a reference, 2 the check could not run. These run
without Docker (the hermetic tier points DOCKER_HOST at nothing), so grading
here is static; tests/integration/test_check_command_docker.py grades in Docker.
"""
# pylint: disable=missing-function-docstring
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
EXAMPLES = ROOT / "docs/contracts/v1/examples"
WEB_REFERENCE = ROOT / "examples/assets/web_dev"
NO_DOCKER = "unix:///nonexistent/onb06-check.sock"


def check(*arguments, cwd=ROOT):
    environment = {**os.environ, "DOCKER_HOST": NO_DOCKER}
    return subprocess.run([sys.executable, "-m", "execution_host.check", *map(str, arguments)], cwd=cwd,
                          env=environment, capture_output=True, text=True, timeout=120, check=False)


def write(path: Path, value) -> Path:
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def test_a_valid_definition_exits_zero_and_states_its_execution_budget():
    result = check(EXAMPLES / "python-io.json")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "is valid" in result.stdout
    # COR-02: the derived budget and the host maximum (sandbox_config.yml running_timeout).
    assert "python: 1 process, sandbox lifetime up to 92 s; this host grants 900 s" in result.stdout
    assert result.stderr == ""


def test_a_static_definition_needs_no_sandbox():
    result = check(EXAMPLES / "webdev.json")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "no sandbox" in result.stdout


@pytest.mark.parametrize("name,lines", [
    ("base-weight-not-100.json",
     ["criteria.base.weight: base weight must equal 100; bonus and penalty weights are caps [INVALID_DEFINITION]"]),
    ("preparation-language-not-allowed.json", ["preparation.languages.java: preparation for `java`"]),
    ("misspelled-template.json", [
        "templates[0]: Unknown template `web_dev`; did you mean `webdev`? [UNKNOWN_TEMPLATE]",
        "criteria.base.tests[0].type: Evaluator `has_tag` is provided by template `webdev`"]),
    ("web-parameter-typo.json",
     ["criteria.base.tests[0].parameters.tagg: `has_tag` has no parameter `tagg`; did you mean `tag`?"]),
])
def test_an_invalid_definition_exits_one_with_each_error_at_its_path(name, lines):
    result = check(EXAMPLES / "invalid" / name)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "is invalid" in result.stdout
    for line in lines:
        assert line in result.stdout, result.stdout
    assert "Traceback" not in result.stdout + result.stderr


def test_every_documented_invalid_example_fails_and_every_valid_one_passes():
    for path in sorted(EXAMPLES.glob("*.json")):
        assert check(path).returncode == 0, path
    for expected in json.loads((EXAMPLES / "invalid/manifest.json").read_text(encoding="utf-8")):
        result = check(EXAMPLES / "invalid" / expected["file"])
        assert result.returncode == 1, expected["file"]
        for error in expected["errors"]:
            assert f"{error['message']} [{error['code']}]" in result.stdout


def test_malformed_json_names_the_line_and_column(tmp_path):
    path = tmp_path / "definition.json"
    path.write_text('{\n  "schema_version": "1.0",\n  "templates": [}\n', encoding="utf-8")
    result = check(path)
    assert result.returncode == 1
    assert f"{path}:3:" in result.stdout and "not valid JSON" in result.stdout


@pytest.mark.parametrize("make", [
    lambda tmp: tmp / "missing.json",
    lambda tmp: tmp,  # a directory
], ids=["missing", "directory"])
def test_an_unreadable_definition_cannot_be_checked(tmp_path, make):
    result = check(make(tmp_path))
    assert result.returncode == 2
    assert "cannot read" in result.stderr.lower()
    assert "Traceback" not in result.stderr


@pytest.mark.skipif(os.geteuid() == 0, reason="root reads files without permission")
def test_a_definition_without_read_permission_cannot_be_checked(tmp_path):
    path = write(tmp_path / "definition.json", {})
    path.chmod(0)
    result = check(path)
    assert result.returncode == 2 and "cannot read" in result.stderr.lower()


def test_usage_errors_exit_two():
    assert check().returncode == 2
    assert check(EXAMPLES / "python-io.json", "--min-score", "101").returncode == 2


def test_a_reference_is_graded_with_criterion_scores_and_feedback(tmp_path):
    definition = json.loads((WEB_REFERENCE / "definition.json").read_text(encoding="utf-8"))
    definition["feedback"] = {"enabled": True}
    result = check(write(tmp_path / "definition.json", definition), "--submission", WEB_REFERENCE)
    assert result.returncode == 0, result.stdout + result.stderr
    out = result.stdout
    assert f"Reference {WEB_REFERENCE} (node): completed, score 80.00/100" in out
    assert "html_structure" in out and "95.00" in out  # a subject and its score
    assert re.search(r"\n +80\.00 +base-subjects-0-tests-0  has_tag\n", out)  # a criterion: score, ID, name
    assert "Found 4 of 5 required `<div>` tags." in out  # its report
    assert "# Evaluation Report" in out  # the rendered feedback


def test_disabled_feedback_is_stated_not_rendered(tmp_path):
    definition = json.loads((WEB_REFERENCE / "definition.json").read_text(encoding="utf-8"))
    definition["feedback"]["enabled"] = False
    result = check(write(tmp_path / "definition.json", definition), "--submission", WEB_REFERENCE)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Feedback: disabled" in result.stdout
    assert "# Evaluation Report" not in result.stdout


def test_min_score_fails_a_reference_that_scores_below_it():
    result = check(WEB_REFERENCE / "definition.json", "--submission", WEB_REFERENCE, "--min-score", "100")
    assert result.returncode == 1
    assert "scored 80.00, below --min-score 100" in result.stdout


def test_each_reference_is_graded_and_any_failure_fails_the_check(tmp_path):
    first, second = tmp_path / "first", tmp_path / "second"
    shutil.copytree(WEB_REFERENCE, first)
    shutil.copytree(WEB_REFERENCE, second)
    (second / "index.html").write_text("<html><body></body></html>", encoding="utf-8")
    result = check(WEB_REFERENCE / "definition.json", "--submission", first, "--submission", second,
                   "--min-score", "50")
    assert result.returncode == 1
    assert f"Reference {first} (node): completed, score 80.00/100" in result.stdout
    assert f"Reference {second} (node): completed, score 0.00/100" in result.stdout


def test_an_ambiguous_html_target_is_caught_against_a_reference_project(tmp_path):
    """ONB-H1: a single-file check without `file` on a multi-page site fails before students see it."""
    project = tmp_path / "site"
    project.mkdir()
    (project / "index.html").write_text("<h1>Home</h1>", encoding="utf-8")
    (project / "about.html").write_text("<h1>About</h1>", encoding="utf-8")
    result = check(EXAMPLES / "webdev.json", "--submission", project)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "failed: AMBIGUOUS_FILE_TARGET" in result.stdout


def test_a_missing_required_file_explains_itself(tmp_path):
    project = tmp_path / "site"
    project.mkdir()
    (project / "home.html").write_text("<h1>Home</h1>", encoding="utf-8")
    result = check(EXAMPLES / "webdev.json", "--submission", project)
    assert result.returncode == 1
    assert "failed: REQUIRED_FILE_MISSING" in result.stdout and "index.html" in result.stdout


def test_grading_execution_without_docker_fails_clearly(tmp_path):
    reference = tmp_path / "reference"
    reference.mkdir()
    (reference / "main.py").write_text("print(int(input()) + int(input()))\n", encoding="utf-8")
    result = check(EXAMPLES / "python-io.json", "--submission", reference)
    assert result.returncode == 2
    assert "Docker is not reachable" in result.stderr and "python" in result.stderr
    assert "Traceback" not in result.stderr
    assert "is valid" in result.stdout  # validation still ran and passed


def test_an_unreadable_submission_directory_cannot_be_checked(tmp_path):
    result = check(EXAMPLES / "webdev.json", "--submission", tmp_path / "missing")
    assert result.returncode == 2
    assert "must be an existing readable directory" in result.stderr


def test_a_definition_with_several_languages_needs_one_selected(tmp_path):
    result = check(EXAMPLES / "multi-language-io.json", "--submission", tmp_path)
    assert result.returncode == 2
    assert "--language" in result.stderr and "python, java, node, cpp, c" in result.stderr
    result = check(EXAMPLES / "python-io.json", "--submission", tmp_path, "--language", "java")
    assert result.returncode == 2 and "not allowed" in result.stderr


def test_the_check_runs_from_any_working_directory(tmp_path):
    result = check(EXAMPLES / "python-io.json", cwd=tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "this host grants 900 s" in result.stdout


def test_a_budget_longer_than_the_host_grants_is_a_definition_problem(tmp_path):
    definition = json.loads((EXAMPLES / "python-io.json").read_text(encoding="utf-8"))
    [test] = definition["criteria"]["base"]["tests"]
    definition["criteria"]["base"]["tests"] = [{**test, "id": f"sum-{index}"} for index in range(30)]
    result = check(write(tmp_path / "definition.json", definition))
    assert result.returncode == 1
    assert "languages.python: In python, the worst case" in result.stdout
    assert "[EXECUTION_BUDGET_EXCEEDED]" in result.stdout
