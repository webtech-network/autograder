"""The Author tutorial's assignments grade as it says, in real Docker sandboxes (ONB-05, #431).

Each tutorial assignment (``examples/tutorial/<name>``) has a definition, a good
and a bad submission. The tutorial's score table states what each submission
scores in each language; this suite grades every row through ``DockerHost``,
the host the HTTP API composes, and checks the score. Outcome excerpts on Author
pages must be a subset of the real outcome, and a report excerpt must be the
real report.
"""
# pylint: disable=missing-function-docstring
import json
from pathlib import Path

import pytest

from autograder import Submission, SubmissionFile, evaluate_submission
from autograder.models.language import Language
from execution_host.docker import DockerHost
from tests.sandbox_profiles import sandbox_config
from tests.unit.test_documentation import ROOT, author_pages, blocks, tutorial_score_rows

#: Source files that belong to one language of a multi-language submission directory.
LANGUAGE_FILES = {"c": {".c"}, "java": {".java"}}


@pytest.fixture(scope="module", name="host")
def docker_host(tmp_path_factory):
    config = tmp_path_factory.mktemp("sandbox") / "sandbox.yml"
    config.write_text(sandbox_config(max_sandboxes=4))
    host = DockerHost(mode="local", config_file=str(config))
    yield host
    host.close()


def submission_files(directory, language):
    files = {}
    for path in sorted((ROOT / directory).iterdir()):
        suffixes = LANGUAGE_FILES.get(language)
        if suffixes and path.suffix in set().union(*LANGUAGE_FILES.values()) - suffixes:
            continue
        files[path.name] = SubmissionFile(path.name, path.read_text(encoding="utf-8"))
    return files


def graded(host, directory, language):
    definition = json.loads((ROOT / directory).parent.joinpath("definition.json").read_text(encoding="utf-8"))
    submission = Submission("student", "student", Path(directory).parent.name,
                            submission_files(directory, language), language=Language(language))
    return evaluate_submission(submission, definition=definition, capabilities=host.capabilities)


def test_the_tutorial_table_covers_three_assignments_good_and_bad_in_every_language():
    rows = tutorial_score_rows()
    assert {Path(path).parent.name for path, _, _ in rows} == {"python-io", "web-page", "compiled"}
    assert {(path, language) for path, language, _ in rows if "compiled" in path} == {
        (f"examples/tutorial/compiled/{variant}", language) for variant in ("good", "bad") for language in ("c", "java")}
    for path, _, score in rows:
        assert (score == 100) == path.endswith("good"), path


@pytest.mark.parametrize("directory, language, score", tutorial_score_rows(), ids=str)
def test_each_tutorial_submission_scores_what_the_tutorial_states(host, directory, language, score):
    outcome = graded(host, directory, language)
    assert outcome.status == "completed", outcome.error
    assert outcome.score == score
    assert outcome.feedback.status == "completed" and outcome.feedback.content


def is_subset(excerpt, actual):
    if isinstance(excerpt, dict):
        return isinstance(actual, dict) and all(k in actual and is_subset(v, actual[k]) for k, v in excerpt.items())
    if isinstance(excerpt, list):
        return isinstance(actual, list) and len(excerpt) == len(actual) and all(map(is_subset, excerpt, actual))
    return excerpt == actual


def test_outcome_and_report_excerpts_on_author_pages_are_real(host):
    checked = 0
    for page in author_pages():
        for language, body, kind, directory in blocks(page):
            if kind not in {"outcome", "report"}:
                continue
            definition = json.loads((ROOT / directory).parent.joinpath("definition.json").read_text())
            outcome = graded(host, directory, definition["languages"][0]).model_dump(mode="json")
            if kind == "outcome":
                assert language == "json"
                assert is_subset(json.loads(body), outcome), (page, directory, json.dumps(outcome, indent=1))
            else:
                assert language == "markdown"
                assert body.rstrip("\n") == outcome["feedback"]["content"].rstrip("\n"), (page, directory)
            checked += 1
    assert checked >= 2
