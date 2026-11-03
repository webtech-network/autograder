"""Real-container grading keeps its canonical outcome across result-model refactors (ARC-11).

``canonical_outcome_golden.json`` was recorded by running this module on the
ARC-03 base (before the ARC-07/ARC-11 refactors) with
``AUTOGRADER_RECORD_GOLDEN=1``. The rubric exercises nested subjects, a mixed
group with ``subjects_weight``, zero-weight and all-zero siblings, repeated
display labels containing slashes, bonus and penalty caps and requested feedback
with a learning resource. Each submission is graded in real Docker sandboxes and
the full canonical tree and score must match exactly.

Feedback text must match exactly too, with one documented correction (ARC-11):
the old focus traversal applied a mixed group's ``subjects_weight`` twice, so in
the "partial" run the failed ``artifact`` criterion (10 points lost) was listed
after ``imports``/``loops`` (7.5 points each). The shared scoring traversal
ranks it before them; every block's content is unchanged.
"""
import json
import os
import re
from pathlib import Path

import pytest

from autograder import Submission, SubmissionFile, build_pipeline
from execution_host.docker import DockerHost
from autograder.models.language import Language
from tests.sandbox_profiles import sandbox_config

GOLDEN = Path(__file__).with_name("canonical_outcome_golden.json")
RUN = "python3 main.py"


def io(criterion_id, name, inputs, expected, weight=1):
    return {"id": criterion_id, "type": "expect_output", "name": name, "weight": weight,
            "parameters": {"inputs": inputs, "expected_output": expected, "program_command": RUN}}


DEFINITION = {
    "schema_version": "1.0",
    "templates": ["input_output", "static_analysis"],
    "languages": ["python"],
    "criteria": {
        "base": {"weight": 100, "subjects": [
            {"subject_name": "Program / IO", "weight": 3, "tests": [
                io("sum", "Check / output", ["2", "3"], "5", weight=2),
                io("sum-large", "Check / output", ["10", "20"], "30", weight=1),
                {"id": "no-crash", "type": "dont_fail", "name": "Does not crash", "weight": 0,
                 "parameters": {"user_input": "4", "program_command": RUN}},
            ]},
            {"subject_name": "Quality", "weight": 1, "subjects_weight": 60, "subjects": [
                {"subject_name": "Imports", "weight": 0, "tests": [
                    {"id": "imports", "type": "forbidden_import", "name": "Check / output",
                     "parameters": {"forbidden_imports": ["os"]}}]},
                {"subject_name": "Keywords", "weight": 0, "tests": [
                    {"id": "loops", "type": "forbidden_keyword", "name": "No loops",
                     "parameters": {"forbidden_keywords": ["for_loop"]}}]},
            ], "tests": [
                {"id": "artifact", "type": "expect_file_artifact", "name": "Writes result", "parameters": {
                    "inputs": ["2", "3"], "artifact_path": "out.txt", "expected_content": "sum=5",
                    "program_command": RUN}},
            ]},
        ]},
        "bonus": {"weight": 10, "tests": [io("bonus-sum", "Bonus / large", ["100", "200"], "300")]},
        "penalty": {"weight": 20, "tests": [
            {"id": "no-subprocess", "type": "forbidden_import", "name": "Avoid subprocess",
             "parameters": {"forbidden_imports": ["subprocess"]}}]},
    },
    "feedback": {"enabled": True, "preferences": {
        "general": {"report_title": "Golden report", "show_passed_tests": True, "online_content": [
            {"url": "https://example.com/io", "description": "Reading input", "linked_tests": ["sum"]},
            {"url": "https://example.com/style", "description": "Style", "linked_tests": ["loops"]},
            {"url": "https://example.com/all", "description": "Always", "linked_tests": []}]},
        "default": {"category_headers": {"penalty": "Penalties"}}}},
}

GOOD = ("import sys\nvalues = sys.stdin.read().split()\nt = int(values[0]) + int(values[1])\nprint(t)\n"
        "open('out.txt', 'w').write('sum=%d\\n' % t)\n")
PARTIAL = ("import sys\nimport os\nimport subprocess\nt = 1\nfor x in sys.stdin.read().split():\n    t += int(x)\n"
           "print(t)\nopen('out.txt', 'w').write('sum=%d\\n' % t)\n")
# Correct small sums, wrong large sums, a forbidden import and the penalty import:
# an unclamped weighted grade with a partial bonus miss and an applied penalty.
MIXED = ("import sys\nimport os\nimport subprocess\nvalues = sys.stdin.read().split()\n"
         "t = int(values[0]) + int(values[1])\nprint(t if t < 100 else t + 1)\n"
         "open('out.txt', 'w').write('sum=%d\\n' % t)\n")
SUBMISSIONS = {"good": GOOD, "partial": PARTIAL, "mixed": MIXED}


@pytest.fixture(scope="module")
def docker_host(tmp_path_factory):
    config = tmp_path_factory.mktemp("sandbox") / "sandbox.yml"
    config.write_text(sandbox_config([Language.PYTHON]))
    host = DockerHost(mode="local", config_file=str(config))
    yield host
    host.close()


def canonical(host, source, locale):
    pipeline = build_pipeline(definition=DEFINITION, capabilities=host.capabilities)
    outcome = pipeline.run(Submission("student", "student", "golden", {"main.py": SubmissionFile("main.py", source)},
                                      language=Language.PYTHON, locale=locale)).outcome
    assert outcome.status == "completed", outcome.error
    data = outcome.model_dump(mode="json")
    return {"score": data["score"], "tree": data["tree"], "feedback": data["feedback"]}


def test_real_container_outcomes_match_the_recorded_golden(docker_host):
    actual = {f"{variant}-{locale}": canonical(docker_host, source, locale)
              for variant, source in SUBMISSIONS.items() for locale in ("en", "pt_br")}
    if os.environ.get("AUTOGRADER_RECORD_GOLDEN"):
        GOLDEN.write_text(json.dumps(actual, indent=2, ensure_ascii=False, sort_keys=True) + "\n")
    golden = json.loads(GOLDEN.read_text())
    assert actual.keys() == golden.keys()
    for key, expected in golden.items():
        assert actual[key]["score"] == expected["score"], key
        assert actual[key]["tree"] == expected["tree"], key
        assert actual[key]["feedback"]["status"] == expected["feedback"]["status"] == "completed"
        blocks = feedback_blocks(expected["feedback"]["content"])
        if key.startswith("partial-"):
            artifact = next(block for block in blocks if "out.txt" in block and block.startswith("### "))
            imports = next(block for block in blocks if "'os'" in block)
            blocks.remove(artifact)
            blocks.insert(blocks.index(imports), artifact)
        assert feedback_blocks(actual[key]["feedback"]["content"]) == blocks, key


def feedback_blocks(content):
    """Split a report into its section dividers and per-criterion blocks."""
    return re.split(r"\n(?=### |---\n)", content)
