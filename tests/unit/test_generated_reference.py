"""The evaluator and definition reference is generated from the contracts (ONB-04, #430).

Teachers read ``docs/reference/``; these tests keep it identical to what the
compiler accepts and to what discovery publishes, and keep hand-written copies
of parameter tables from coming back.
"""
# pylint: disable=missing-function-docstring
import importlib.util
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Annotated

import pytest
import yaml
from pydantic import Field

from autograder import (
    EvaluationError, EvaluationInput, Template, TestFunction, TestResult, compile_definition,
    describe_templates, grading_definition_json_schema,
)
from autograder.models.contracts.catalog import CAPABILITY_DESCRIPTIONS
from autograder.services.preparation import check_capabilities
from autograder.translations import translator

ROOT = Path(__file__).resolve().parents[2]
REFERENCE = ROOT / "docs" / "reference"


@pytest.fixture(scope="module", name="generator")
def load_generator():
    spec = importlib.util.spec_from_file_location("generate_reference", ROOT / "scripts" / "generate_reference.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def evaluators():
    return [(template, evaluator) for template in describe_templates().templates for evaluator in template.evaluators]


def section(text, heading_id):
    """The Markdown between the heading with ``{#heading_id}`` and the next heading of that level or above."""
    match = re.search(rf"^(#+) .*\{{#{re.escape(heading_id)}\}}$", text, re.M)
    assert match, heading_id
    level = len(match.group(1))
    end = re.compile(rf"^#{{1,{level}}} ", re.M).search(text, match.end())
    return text[match.end():end.start() if end else len(text)]


def table(text):
    """Rows of the first Markdown table in ``text`` as dicts keyed by its header."""
    lines = [line for line in text.splitlines() if line.startswith("|")]
    if not lines:
        return []
    split = lambda line: [cell.strip() for cell in re.split(r"(?<!\\)\|", line.strip())[1:-1]]  # noqa: E731
    header = split(lines[0])
    return [dict(zip(header, split(line))) for line in lines[2:]]


# --- Drift ---------------------------------------------------------------------

def test_checked_in_reference_matches_the_contracts(generator):
    assert generator.stale_pages(REFERENCE) == []


class Greeting(TestFunction):
    name = "fixture_greeting"
    description = "Checks that a greeting is present."

    def execute(self, evaluation: EvaluationInput, *,
                needle: Annotated[str, Field(min_length=1, description="Text to find.")]) -> TestResult:
        return TestResult(self.name, 100 if any(needle in f.content for f in evaluation.files) else 0, "")


class ChangedGreeting(Greeting):
    """The same evaluator after a contract change: the parameter gained a default."""

    def execute(self, evaluation: EvaluationInput, *,
                needle: Annotated[str, Field(min_length=1, description="Text to find.")] = "Hello") -> TestResult:
        return super().execute(evaluation, needle=needle)


def test_drift_check_fails_when_a_contract_changes_without_regeneration(generator, tmp_path):
    before = {"fixture": Template("Fixture", "A fixture template.", [Greeting()])}
    after = {"fixture": Template("Fixture", "A fixture template.", [ChangedGreeting()])}
    generator.write_pages(tmp_path, before)
    assert generator.stale_pages(tmp_path, before) == []
    assert "`fixture_greeting`" in (tmp_path / "evaluators.md").read_text(encoding="utf-8")

    assert generator.stale_pages(tmp_path, after) == [tmp_path / "evaluators.md"]
    generator.write_pages(tmp_path, after)
    assert generator.stale_pages(tmp_path, after) == []


def test_check_command_fails_on_an_edited_page_and_names_the_fix(generator, tmp_path):
    generator.write_pages(tmp_path)
    page = tmp_path / "definition.md"
    page.write_text(page.read_text(encoding="utf-8").replace("show_score", "show_scores"), encoding="utf-8")
    with pytest.raises(SystemExit) as failed:
        generator.main(["--check", "--output", str(tmp_path)])
    assert failed.value.code != 0
    generator.main(["--output", str(tmp_path)])
    generator.main(["--check", "--output", str(tmp_path)])


def test_missing_page_is_stale(generator, tmp_path):
    assert generator.stale_pages(tmp_path) == [tmp_path / "definition.md", tmp_path / "evaluators.md"]


def test_generation_is_byte_identical_across_runs_and_interpreter_processes(generator, tmp_path):
    first = generator.render_pages()
    assert generator.render_pages() == first
    for seed in ("0", "1", "4242"):
        output = tmp_path / seed
        subprocess.run([sys.executable, str(ROOT / "scripts" / "generate_reference.py"), "--output", str(output)],
                       cwd=ROOT, check=True, env={**os.environ, "PYTHONHASHSEED": seed})
        assert {path.name: path.read_bytes() for path in output.iterdir()} == {
            name: text.encode("utf-8") for name, text in first.items()}


def test_drift_check_runs_in_the_hermetic_verify_path():
    plan = subprocess.run(["make", "-n", "verify"], cwd=ROOT, capture_output=True, text=True, check=True).stdout
    assert "scripts/generate_reference.py --check" in plan


# --- Evaluator reference -------------------------------------------------------

def test_every_discovery_evaluator_appears_with_correct_required_and_default_flags():
    text = (REFERENCE / "evaluators.md").read_text(encoding="utf-8")
    for template, evaluator in evaluators():
        body = section(text, evaluator.identifier)
        assert f"`{template.identifier}`" in body, evaluator.identifier
        schema = evaluator.parameters_schema
        rows = {row["Parameter"].strip("`"): row for row in table(body)}
        assert set(rows) == set(schema["properties"]), evaluator.identifier
        for name, row in rows.items():
            required = name in schema.get("required", [])
            assert row["Required"] == ("yes" if required else "no"), (evaluator.identifier, name)
            if required:
                assert row["Default"] == "—", (evaluator.identifier, name)
            else:
                expected = json.dumps(schema["properties"][name]["default"], ensure_ascii=False)
                assert row["Default"] == f"`{expected}`", (evaluator.identifier, name)
            assert row["Description"] == schema["properties"][name]["description"].replace("|", "\\|")


def test_every_optional_discovery_parameter_publishes_the_default_compilation_applies():
    for _, evaluator in evaluators():
        schema = evaluator.parameters_schema
        optional = set(schema["properties"]) - set(schema.get("required", []))
        normalized = compile_definition({
            "schema_version": "1.0", "templates": ["input_output", "api", "webdev", "static_analysis"],
            "languages": ["python"], "criteria": {"base": {"weight": 100, "tests": [{
                "id": "x", "type": evaluator.identifier, "name": "x",
                "parameters": {k: v for k, v in evaluator.sample_parameters.items() if k not in optional}}]}},
        }) if evaluator.identifier != "forbidden_keyword" else None
        for name in optional:
            assert "default" in schema["properties"][name], (evaluator.identifier, name)
            if normalized is not None:
                [test] = normalized.definition.criteria.base.tests
                assert test.parameters[name] == schema["properties"][name]["default"], (evaluator.identifier, name)


def foreign_catalog_strings():
    """Strings that exist only in a non-default locale catalog (for example Portuguese)."""
    def strings(value):
        if isinstance(value, dict):
            return {s for item in value.values() for s in strings(item)}
        return {value} if isinstance(value, str) else set()
    default = strings(translator._CATALOGS[translator.DEFAULT_LOCALE])  # pylint: disable=protected-access
    return {s for locale, catalog in translator._CATALOGS.items()  # pylint: disable=protected-access
            if locale is not translator.DEFAULT_LOCALE for s in strings(catalog)} - default


def test_every_discovery_text_is_a_nonempty_default_locale_description():
    foreign = foreign_catalog_strings()
    assert foreign, "the check needs a non-default catalog to compare against"
    texts = []
    for template in describe_templates().templates:
        texts += [(template.identifier, template.description)]
        for evaluator in template.evaluators:
            texts += [(evaluator.identifier, evaluator.description)]
            for name, schema in evaluator.parameters_schema["properties"].items():
                texts += [(f"{evaluator.identifier}.{name}", schema.get("description", ""))]
    for where, text in texts:
        assert text.strip(), f"{where} has no description"
        assert text not in foreign, f"{where} is described in a non-default locale: {text!r}"
    assert "Um template" not in json.dumps(texts)


def test_generated_criterion_examples_compile_as_written():
    text = (REFERENCE / "evaluators.md").read_text(encoding="utf-8")
    catalog = {e.identifier: t.identifier for t, e in evaluators()}
    examples = [json.loads(block) for block in re.findall(r"```json\n(.*?)```", text, re.S)]
    assert sorted(example["type"] for example in examples) == sorted(catalog)
    for criterion in examples:
        compile_definition({"schema_version": "1.0", "templates": [catalog[criterion["type"]]],
                            "languages": ["python"], "criteria": {"base": {"weight": 100, "tests": [criterion]}}})


def shipped_unavailable():
    from execution_host.docker import DockerHost  # pylint: disable=import-outside-toplevel
    unavailable = {}
    for capability in CAPABILITY_DESCRIPTIONS:
        try:
            check_capabilities(frozenset({capability}), DockerHost().capabilities)
        except EvaluationError as error:
            unavailable[capability] = error.code
    return unavailable


def test_evaluators_needing_a_capability_no_shipped_host_provides_are_visibly_marked():
    unavailable = shipped_unavailable()
    assert unavailable == {"http_network": "SERVER_CAPABILITY_UNAVAILABLE"}
    text = (REFERENCE / "evaluators.md").read_text(encoding="utf-8")
    marked = set()
    for _, evaluator in evaluators():
        body = section(text, evaluator.identifier)
        warning = '!!! warning "Not available on the shipped hosts"' in body
        if warning:
            marked.add(evaluator.identifier)
        assert warning == bool(set(evaluator.required_capabilities) & set(unavailable)), evaluator.identifier
    assert marked == {"health_check", "check_response_json"}
    assert '!!! warning "Not available on the shipped hosts"' in section(text, "api").split("###")[0]
    assert "SERVER_CAPABILITY_UNAVAILABLE" in section(text, "health_check")


def test_both_shipped_hosts_compose_the_docker_host_the_reference_describes():
    for host in ("web/core/host.py", "github_action/github_action_service.py"):
        assert "from execution_host.docker import DockerHost" in (ROOT / host).read_text(encoding="utf-8"), host


# --- Definition reference ------------------------------------------------------

def definition_objects():
    schema = grading_definition_json_schema()
    return {"GradingDefinition": schema, **{name: value for name, value in schema["$defs"].items()
                                            if "properties" in value and not name.endswith("Parameters")}}


def test_every_definition_field_has_a_description_type_and_default():
    text = (REFERENCE / "definition.md").read_text(encoding="utf-8")
    for name, schema in definition_objects().items():
        assert schema.get("description", "").strip(), f"{name} has no description"
        rows = {row["Field"].strip("`"): row for row in table(section(text, name.lower()))}
        assert set(rows) == set(schema["properties"]), name
        for field, prop in schema["properties"].items():
            assert prop.get("description", "").strip(), f"{name}.{field} has no description"
            assert rows[field]["Type"], (name, field)
            required = field in schema.get("required", [])
            assert rows[field]["Required"] == ("yes" if required else "no"), (name, field)
            assert required or "default" in prop, f"{name}.{field} publishes no default"


@pytest.mark.parametrize("field, kind, default", [
    ("report_title", "string or null", "`null`"),
    ("show_score", "boolean", "`true`"),
    ("show_passed_tests", "boolean", "`false`"),
    ("add_report_summary", "boolean", "`true`"),
    ("online_content", "list of [LearningResource](#learningresource)", "`[]`"),
])
def test_feedback_general_preferences_are_documented_with_types_and_defaults(field, kind, default):
    text = (REFERENCE / "definition.md").read_text(encoding="utf-8")
    rows = {row["Field"]: row for row in table(section(text, "generalpreferences"))}
    assert (rows[f"`{field}`"]["Type"], rows[f"`{field}`"]["Default"]) == (kind, default)


def test_feedback_category_headers_are_documented_with_type_and_default():
    text = (REFERENCE / "definition.md").read_text(encoding="utf-8")
    [row] = table(section(text, "defaultpreferences"))
    assert row["Field"] == "`category_headers`" and row["Default"] == "`{}`"
    assert "`base`" in row["Type"] and "`penalty`" in row["Type"]


# --- Documentation shape -------------------------------------------------------

def test_no_hand_maintained_parameter_tables_remain_under_docs():
    offenders = []
    for path in sorted((ROOT / "docs").rglob("*.md")):
        if path.parent == REFERENCE:
            continue
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if re.match(r"^\|\s*Parameter\s*\|", line):
                offenders.append(f"{path.relative_to(ROOT)}:{number}")
    assert offenders == []


def test_generated_pages_say_they_are_generated_and_are_in_the_nav():
    nav = json.dumps(yaml.safe_load((ROOT / "mkdocs.yml").read_text(encoding="utf-8"))["nav"])
    for page in ("evaluators.md", "definition.md"):
        assert f"reference/{page}" in nav, page
        assert "scripts/generate_reference.py" in "".join((REFERENCE / page).read_text(encoding="utf-8").splitlines(True)[:5])
