"""Architecture checks that protect responsibilities (ARC-14, #394).

They check who may depend on whom, that discovery and the documented examples
agree with the registry, and that the documented extension path works with
only an implementation, a parameter contract and a registration. They do not
enforce class counts, folder layouts or a framework.
"""
# pylint: disable=missing-function-docstring
import ast
import json
import re
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import pytest

import autograder
from autograder import (
    DefinitionValidationError, HostCapabilities, Submission, SubmissionFile, compile_definition,
    describe_templates, evaluate_submission,
)
from autograder.models.process import ProcessResult, ProcessStatus
from autograder.template_library import BUILTIN_TEMPLATES
from examples.contracts import custom_evaluator, execution_evaluator, host_provider

ROOT = Path(__file__).resolve().parents[2]

#: Concrete hosts, infrastructure and provider SDKs. Core receives all of them
#: through ``HostCapabilities``; it never constructs or imports them.
HOST_AND_PROVIDER_MODULES = {
    "web", "github_action", "execution_host", "sandbox_manager",
    "boto3", "botocore", "docker", "openai", "fastapi", "starlette", "uvicorn",
    "sqlalchemy", "alembic", "requests", "httpx",
}
#: Layer -> packages it must not import. Hosts compose infrastructure, never the reverse.
FORBIDDEN_IMPORTS = {
    "autograder": HOST_AND_PROVIDER_MODULES,
    "sandbox_manager": {"web", "github_action", "execution_host"},
    "execution_host": {"web", "github_action"},
}


def imported_roots(path: Path):
    """Top-level modules imported anywhere in a file, including inside functions."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield node.lineno, alias.name.split(".")[0]
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            yield node.lineno, node.module.split(".")[0]


@pytest.mark.parametrize("package", sorted(FORBIDDEN_IMPORTS))
def test_layers_do_not_import_the_hosts_that_compose_them(package):
    violations = [
        f"{path.relative_to(ROOT)}:{line} imports {module}"
        for path in sorted((ROOT / package).rglob("*.py"))
        for line, module in imported_roots(path)
        if module in FORBIDDEN_IMPORTS[package]
    ]
    assert violations == []


def test_importing_every_core_module_loads_no_host_or_provider_package():
    """Catches indirect imports (re-exports, importlib) that the AST scan cannot see."""
    script = (
        "import importlib, pkgutil, sys, autograder\n"
        "for info in pkgutil.walk_packages(autograder.__path__, 'autograder.'):\n"
        "    importlib.import_module(info.name)\n"
        f"print(sorted({{name.split('.')[0] for name in sys.modules}} & {HOST_AND_PROVIDER_MODULES!r}))\n"
    )
    loaded = subprocess.run([sys.executable, "-c", script], cwd=ROOT, capture_output=True,
                            text=True, check=True).stdout.strip()
    assert loaded == "[]"


# --- Discovery and the documented examples agree with the registry ---------------

EXAMPLE_TEMPLATES = {"trusted_text": custom_evaluator.TEMPLATE,
                     "program_checks": execution_evaluator.TEMPLATE}


def test_catalog_describes_the_example_evaluators_from_their_own_contracts():
    catalog = describe_templates(EXAMPLE_TEMPLATES)
    described = {t.identifier: t for t in catalog.templates}
    for identifier, template in EXAMPLE_TEMPLATES.items():
        entries = {e.identifier: e for e in described[identifier].evaluators}
        assert set(entries) == set(template.get_tests())
        for name, function in template.get_tests().items():
            assert entries[name].parameters_schema == {
                **function.config_schema.model_json_schema(), "additionalProperties": False}
            assert entries[name].required_capabilities == sorted(function.required_capabilities)
    contains = described["trusted_text"].evaluators[0]
    assert contains.parameters_schema["required"] == ["needle"]
    assert contains.parameters_schema["properties"]["needle"]["minLength"] == 1
    assert described["program_checks"].evaluators[0].required_capabilities == ["sandbox_execution"]
    # Trusted examples are local to the call: built-in discovery is unchanged.
    builtin = {e.identifier for t in describe_templates().templates for e in t.evaluators}
    assert not {"contains_text", "prints_line"} & builtin


@pytest.mark.parametrize("module", [custom_evaluator, execution_evaluator], ids=lambda m: m.__name__)
def test_catalog_sample_parameters_compile_for_each_example(module):
    identifier = module.DEFINITION["templates"][0]
    template = EXAMPLE_TEMPLATES[identifier]
    for evaluator in describe_templates({identifier: template}).templates[-1].evaluators:
        value = deepcopy(module.DEFINITION)
        value["criteria"]["base"]["tests"][0].update(type=evaluator.identifier,
                                                     parameters=evaluator.sample_parameters)
        compile_definition(value, templates={identifier: template})


def documentation_files():
    return [ROOT / "AGENTS.md", ROOT / "README.md", ROOT / "CONTRIBUTING.md",
            *sorted((ROOT / "docs").rglob("*.md")), *sorted((ROOT / "examples").rglob("*.md"))]


def test_documented_example_commands_name_existing_runnable_modules():
    documented = set()
    for path in documentation_files():
        documented.update(re.findall(r"python -m (examples\.[\w.]+)", path.read_text(encoding="utf-8")))
    assert {"examples.contracts.custom_evaluator", "examples.contracts.execution_evaluator"} <= documented
    for module in documented:
        source = ROOT / (module.replace(".", "/") + ".py")
        assert source.is_file(), module
        assert '__name__ == "__main__"' in source.read_text(encoding="utf-8"), module


def test_extension_recipe_table_matches_discovery():
    """The recipe's example table states identifiers and capabilities; discovery must agree."""
    recipe = (ROOT / "docs/architecture/extending.md").read_text(encoding="utf-8")
    rows = re.findall(r"^\| `(examples/contracts/\w+\.py)` \| `(\w+)` \| `(\w+)` \| (.*?) \|$", recipe, re.M)
    assert rows, "the recipe must list its examples"
    catalog = describe_templates(EXAMPLE_TEMPLATES)
    evaluators = {e.identifier: e for t in catalog.templates for e in t.evaluators}
    for path, template_id, evaluator_id, capabilities in rows:
        assert (ROOT / path).is_file()
        assert evaluator_id in EXAMPLE_TEMPLATES[template_id].get_tests()
        assert re.findall(r"`(\w+)`", capabilities) == evaluators[evaluator_id].required_capabilities


def test_builtin_checklist_names_tests_that_ci_runs():
    """Each checklist step names the test that enforces it; those tests must exist."""
    recipe = (ROOT / "docs/architecture/extending.md").read_text(encoding="utf-8")
    section = recipe[recipe.index("## Built-in evaluator checklist"):recipe.index("## Evaluators that run code")]
    rows = re.findall(r"^\| (?!Step|---)(.+?) \| (.+?) \|$", section, re.M)
    assert len(rows) >= 6
    for step, enforced in rows:
        references = re.findall(r"`(tests/(?:unit|web)/[\w/]+\.py)::(\w+)`", enforced)
        assert references, step
        for path, test in references:
            source = ast.parse((ROOT / path).read_text(encoding="utf-8"))
            assert test in {node.name for node in ast.walk(source) if isinstance(node, ast.FunctionDef)}, (path, test)


# --- The documented extension path ---------------------------------------------

def example_imports(module):
    return {name for _, name in imported_roots(Path(module.__file__))} | {
        node.module for node in ast.walk(ast.parse(Path(module.__file__).read_text(encoding="utf-8")))
        if isinstance(node, ast.ImportFrom) and node.module}


#: What an evaluator author needs, importable from ``autograder`` alone (ONB-08).
AUTHORING_SURFACE = {
    "Template", "TestFunction", "AiTestFunction", "EvaluationInput", "ParameterIssue", "TestResult",
    "Submission", "SubmissionFile", "Language", "HostCapabilities", "ExecutionSession", "ServerSession",
    "EvaluationError", "ProcessRequest", "ProcessResult", "ProcessStatus", "lines_to_stdin", "split_command",
    "BaseExecutionTest",
}


def test_public_surface_exports_everything_an_evaluator_author_needs():
    assert AUTHORING_SURFACE <= set(autograder.__all__)
    assert len(autograder.__all__) == len(set(autograder.__all__))
    for name in autograder.__all__:
        assert getattr(autograder, name) is not None, name
    assert autograder.BaseExecutionTest.required_capabilities == ("sandbox_execution",)


@pytest.mark.parametrize("module", [custom_evaluator, execution_evaluator, host_provider], ids=lambda m: m.__name__)
def test_examples_import_only_from_the_public_autograder_package(module):
    imports = example_imports(module)
    assert not imports & HOST_AND_PROVIDER_MODULES
    # Nothing under autograder.models, autograder.services, autograder.template_library or any other submodule.
    assert {name for name in imports if name.startswith("autograder.")} == set()
    tree = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
    names = {alias.name for node in ast.walk(tree)
             if isinstance(node, ast.ImportFrom) and node.module == "autograder" for alias in node.names}
    assert names and names <= set(autograder.__all__)


def test_static_evaluator_needs_no_capability_and_opens_no_session():
    assert custom_evaluator.grade("<h1>Hello</h1>").score == 100
    assert custom_evaluator.grade("<h1>Bye</h1>").score == 0
    acquired = []
    outcome = evaluate_submission(
        Submission("local", "local", "x", {"index.html": SubmissionFile("index.html", "Hello")}),
        definition=custom_evaluator.DEFINITION, templates={"trusted_text": custom_evaluator.TEMPLATE},
        capabilities=HostCapabilities(execution=acquired.append))
    assert outcome.status == "completed" and not acquired
    bad = deepcopy(custom_evaluator.DEFINITION)
    bad["criteria"]["base"]["tests"][0]["parameters"] = {"needle": ""}
    with pytest.raises(DefinitionValidationError):
        compile_definition(bad, templates={"trusted_text": custom_evaluator.TEMPLATE})


def test_execution_evaluator_runs_through_one_owned_fake_session():
    sessions = []
    outcome = execution_evaluator.grade(
        "print('Hello, ' + input())",
        ProcessResult(ProcessStatus.EXITED, 0, stdout="Hello, Ada\n"), sessions)
    assert outcome.status == "completed" and outcome.score == 100
    assert len(sessions) == 1
    session = sessions[0]
    assert session.closed == 1 and set(session.files) == {"main.py"}
    [request] = session.requests
    assert request.argv == ("python3", "main.py") and request.shell is None and request.stdin == b"Ada\n"


@pytest.mark.parametrize("result, status, score, code", [
    (ProcessResult(ProcessStatus.EXITED, 1, stdout="Traceback"), "completed", 0, None),
    (ProcessResult(ProcessStatus.TIMED_OUT, None), "completed", 0, None),
    (ProcessResult(ProcessStatus.NOT_STARTED, missing_executable="python3"), "failed", None,
     "PROCESS_START_FAILED"),
], ids=["student-failure", "timeout", "not-started"])
def test_execution_evaluator_separates_assessed_zero_from_infrastructure_failure(result, status, score, code):
    sessions = []
    outcome = execution_evaluator.grade("pass", result, sessions)
    assert (outcome.status, outcome.score) == (status, score)
    assert (outcome.error.code if outcome.error else None) == code
    assert [session.closed for session in sessions] == [1]


def test_execution_evaluator_without_a_host_capability_fails_before_acquisition():
    outcome = evaluate_submission(
        Submission("local", "local", "x", {"main.py": SubmissionFile("main.py", "pass")}),
        definition=execution_evaluator.DEFINITION,
        templates={"program_checks": execution_evaluator.TEMPLATE},
        capabilities=HostCapabilities())
    assert outcome.status == "failed" and outcome.error.code == "CAPABILITY_UNAVAILABLE"


def test_execution_evaluator_rejects_malformed_commands_at_compilation():
    bad = deepcopy(execution_evaluator.DEFINITION)
    bad["criteria"]["base"]["tests"][0]["parameters"]["program_command"] = "python3 'main.py"
    with pytest.raises(DefinitionValidationError) as caught:
        compile_definition(bad, templates={"program_checks": execution_evaluator.TEMPLATE})
    assert caught.value.errors()[0]["code"] == "INVALID_COMMAND"


def test_registration_is_local_and_needs_no_engine_change():
    """Adding the examples changed no built-in registry or generic dispatch."""
    assert not set(EXAMPLE_TEMPLATES) & set(BUILTIN_TEMPLATES)


def test_readme_template_tables_name_registered_evaluators_and_parameters():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    section = readme[readme.index("## Grading Templates"):readme.index("#### 4. Custom Templates")]
    evaluators = {e.identifier: e for t in describe_templates().templates for e in t.evaluators}
    rows = re.findall(r"^\| `(\w+)` +\|[^|]*\|([^|]*)\|", section, re.M)
    assert len(rows) >= 8
    for identifier, parameters in rows:
        assert identifier in evaluators, identifier
        properties = evaluators[identifier].parameters_schema["properties"]
        assert set(re.findall(r"`(\w+)`", parameters)) <= set(properties), identifier


def test_template_reference_criterion_snippets_compile():
    """Every criterion snippet in the template reference compiles as written."""
    catalog = {e.identifier: t.identifier for t in describe_templates().templates for e in t.evaluators}
    checked = 0
    for path in sorted((ROOT / "docs/template-library").glob("*.md")):
        for block in re.findall(r"```json\n(.*?)```", path.read_text(encoding="utf-8"), re.S):
            criterion = json.loads(block)
            if not {"type", "parameters"} <= set(criterion):
                continue
            definition = {"schema_version": "1.0", "templates": [catalog[criterion["type"]]],
                          "languages": ["python"], "criteria": {"base": {"weight": 100, "tests": [criterion]}}}
            compile_definition(definition)
            checked += 1
    assert checked >= 15


def test_criteria_tree_guide_example_compiles():
    guide = (ROOT / "docs/core/criteria-tree.md").read_text(encoding="utf-8")
    [block] = [b for b in re.findall(r"```json\n(.*?)```", guide, re.S) if '"base"' in b]
    compile_definition({"schema_version": "1.0", "templates": ["input_output", "static_analysis"],
                        "languages": ["python"], "criteria": json.loads(block)})


def test_quickstart_configuration_is_a_valid_definition():
    guide = (ROOT / "docs/getting-started/first-grading-workflow.md").read_text(encoding="utf-8")
    body = json.loads(re.findall(r"-d '(\{.*?\})'", guide, re.S)[0])
    assert set(body) == {"external_assignment_id", "definition"}
    compile_definition(body["definition"])
