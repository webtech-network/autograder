"""ARC-05: one domain language declaration; hosts, evaluators and parsers own the rest."""
import ast
import json
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from autograder import (
    Submission, SubmissionFile, build_pipeline, compile_definition, grading_definition_json_schema,
    outcome_json_schema, select_language, DefinitionValidationError,
)
from autograder.models.language import LANGUAGE_IDS, Language
from sandbox_manager.api import ControlSettings, create_app
from sandbox_manager.errors import RuntimeUnavailableError
from sandbox_manager.manager import SandboxManager
from sandbox_manager.models.pool_config import SandboxHostConfig, SandboxPoolConfig, runtime_images
from sandbox_manager.remote_client import RemoteSandboxManager
from tests.sandbox_profiles import TEST_IMAGES, sandbox_config
from tests.unit.sandbox.fakes import FakeDocker, owner, pool_config
from web.schemas.execution import DeliberateCodeExecutionRequest
from web.schemas.submission import SubmissionCreate

ROOT = Path(__file__).resolve().parents[2]
TOKEN = "language-token-" + "z" * 20


def definition(languages, tests=None, templates=("input_output",)):
    return {"schema_version": "1.0", "templates": list(templates), "languages": list(languages),
            "criteria": {"base": {"weight": 100, "tests": tests or [
                {"id": "run", "type": "dont_fail", "name": "Runs", "parameters": {"program_command": "CMD"}}]}}}


# ----- one canonical declaration ------------------------------------------------------

def test_domain_language_carries_no_runtime_and_imports_no_infrastructure():
    assert [language.value for language in Language] == list(LANGUAGE_IDS)
    assert not any(hasattr(language, "image") for language in Language)
    tree = ast.parse((ROOT / "autograder/models/language.py").read_text())
    imported = {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
    imported |= {alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names}
    assert imported == {"enum", "typing"}


def test_no_hand_maintained_language_lists_remain_in_product_code():
    """Every list of identifiers derives from Language; only the declaration spells them out."""
    pattern = r'''["']python["'],\s*["'](java|node|c|cpp)["']'''
    found = subprocess.run(["grep", "-rEn", pattern, "autograder", "web", "github_action", "execution_host",
                            "sandbox_manager", "--include=*.py"], cwd=ROOT, capture_output=True, text=True)
    assert found.stdout == ""


def _enums(schema):
    if isinstance(schema, dict):
        if "enum" in schema and "python" in schema["enum"]:
            yield schema["enum"]
        for value in schema.values():
            yield from _enums(value)
    elif isinstance(schema, list):
        for value in schema:
            yield from _enums(value)


@pytest.mark.parametrize("schema", [grading_definition_json_schema, outcome_json_schema])
def test_json_contracts_derive_their_identifiers_from_the_declaration(schema):
    enums = list(_enums(schema()))
    assert enums and all(enum == list(LANGUAGE_IDS) for enum in enums)


def test_checked_in_wire_schemas_keep_the_existing_identifiers():
    for name in ("grading-definition.schema.json", "terminal-outcome.schema.json"):
        enums = list(_enums(json.loads((ROOT / "docs/contracts/v1" / name).read_text())))
        assert enums and all(set(enum) == {"python", "java", "node", "cpp", "c"} for enum in enums)


def test_http_inputs_validate_against_the_declaration():
    files = [{"filename": "main.py", "content": "print(1)"}]
    base = {"external_assignment_id": "a", "external_user_id": "u", "username": "u", "files": files}
    for language in LANGUAGE_IDS:
        assert SubmissionCreate(**base, language=language).language == language
        DeliberateCodeExecutionRequest(language=language, submission_files=files, program_command="true")
    # The submission adapter normalizes case into the canonical identifier; nothing else is accepted.
    assert SubmissionCreate(**base, language="Java").language == "java"
    for invalid in ("rust", "javascript", "py", ""):
        with pytest.raises(ValueError):
            SubmissionCreate(**base, language=invalid)
    with pytest.raises(ValueError):
        DeliberateCodeExecutionRequest(language="Python", submission_files=files, program_command="true")


# ----- the language is bound once per execution ----------------------------------------

def test_single_language_definitions_infer_the_language():
    assert select_language(compile_definition(definition(["java"]))) is Language.JAVA


def test_multilingual_definitions_require_an_explicit_language():
    compiled = compile_definition(definition(["python", "java"]))
    with pytest.raises(DefinitionValidationError) as failure:
        select_language(compiled)
    assert failure.value.errors()[0]["code"] == "LANGUAGE_REQUIRED"
    assert select_language(compiled, "java") is Language.JAVA
    assert select_language(compiled, Language.PYTHON) is Language.PYTHON


@pytest.mark.parametrize("value", ["c", Language.NODE, "rust"])
def test_disallowed_or_unknown_languages_are_rejected(value):
    with pytest.raises(DefinitionValidationError) as failure:
        select_language(compile_definition(definition(["python", "java"])), value)
    assert failure.value.errors()[0]["code"] == "LANGUAGE_NOT_ALLOWED"


def test_the_bound_language_reaches_the_evaluator_and_the_outcome():
    seen = []

    class Session:
        fixture_root = "/tmp/app"

        def prepare_workdir(self, files):
            pass

        def run_process(self, request):
            from tests.process_results import exited
            seen.append(" ".join(request.argv))
            return exited()

        def close(self):
            pass

    from autograder import HostCapabilities
    acquired = []
    capabilities = HostCapabilities(execution=lambda language, budget: acquired.append(language) or Session())
    pipeline = build_pipeline(definition=definition(["java"]), capabilities=capabilities)
    outcome = pipeline.run(Submission("s", "s", "a", {"Main.java": SubmissionFile("Main.java", "")})).outcome
    assert outcome.status == "completed" and outcome.language == "java"
    assert acquired == [Language.JAVA] and seen == ["java Main"]


# ----- the host owns runtime images ----------------------------------------------------

def test_runtime_images_come_only_from_the_host_profile(tmp_path):
    path = tmp_path / "sandbox.yml"
    path.write_text(sandbox_config((Language.PYTHON,)).replace(TEST_IMAGES[Language.PYTHON], "registry.local/py:3.13"))
    configs = SandboxHostConfig.load_from_yaml(str(path)).pools
    assert [(config.language, config.image) for config in configs] == [(Language.PYTHON, "registry.local/py:3.13")]


def test_shipped_host_profile_covers_every_domain_language():
    assert set(runtime_images(__import__("yaml").safe_load((ROOT / "sandbox_config.yml").read_text())["runtimes"])) == set(Language)


@pytest.mark.parametrize("runtimes,message", [(None, "runtimes"), ({"rust": "x"}, "unknown runtime language"),
                                              ({"python": ""}, "needs an image")])
def test_invalid_runtime_profiles_are_rejected(runtimes, message):
    with pytest.raises(ValueError, match=message):
        runtime_images(runtimes)


def test_shipped_pool_uses_the_profile_image():
    docker = FakeDocker()
    config = SandboxPoolConfig(language=Language.C, image="custom-c:1", pool_size=1, running_timeout=60)
    manager = SandboxManager([config], docker, max_sandboxes=2, owner=owner(), reclaim_orphans=False,
                             monitor_interval=60)
    try:
        # Each creation attempt (gVisor, then the default runtime) uses the profile image.
        assert {call["image"] for call in docker.containers.run_calls} == {"custom-c:1"}
    finally:
        manager.shutdown()


def test_missing_local_runtime_is_a_capability_failure_not_an_invalid_language():
    manager = SandboxManager([pool_config(Language.PYTHON)], FakeDocker(), max_sandboxes=2, owner=owner(),
                             reclaim_orphans=False,
                             monitor_interval=60)
    try:
        with pytest.raises(RuntimeUnavailableError, match="c"):
            manager.get_sandbox(Language.C)
        assert isinstance(RuntimeUnavailableError("x"), RuntimeError)  # the engine's capability mapping
        assert not isinstance(RuntimeUnavailableError("x"), ValueError)  # never an invalid-input error
    finally:
        manager.shutdown()


def test_missing_remote_runtime_has_a_distinct_code_and_client_error():
    def manager_factory():
        return SandboxManager([pool_config(Language.PYTHON)], FakeDocker(), max_sandboxes=2, owner=owner(), reclaim_orphans=False,
                              monitor_interval=60)
    app = create_app(ControlSettings(token=TOKEN), manager_factory=manager_factory)
    with TestClient(app, headers={"Authorization": f"Bearer {TOKEN}"}) as client:
        missing = client.post("/sandboxes/c", json={"request_id": "r" * 32})
        assert missing.status_code == 501 and missing.json()["detail"]["code"] == "RUNTIME_UNAVAILABLE"
        unknown = client.post("/sandboxes/rust", json={"request_id": "r" * 32})
        assert unknown.status_code == 422
        remote = RemoteSandboxManager("http://control", TOKEN)
        remote._session = client  # pylint: disable=protected-access  # same wire, in process
        with pytest.raises(RuntimeUnavailableError):
            remote.get_sandbox(Language.C)


def test_pipeline_reports_missing_runtime_as_capability_unavailable():
    from autograder import HostCapabilities

    def execution(language):
        raise RuntimeUnavailableError(f"No sandbox runtime is configured for {language.value}")
    pipeline = build_pipeline(definition=definition(["python", "c"]), capabilities=HostCapabilities(execution=execution))
    outcome = pipeline.run(Submission("s", "s", "a", {"main.c": SubmissionFile("main.c", "")},
                                      language=Language.C)).outcome
    assert outcome.status == "failed" and outcome.language == "c"
    assert outcome.error.code == "CAPABILITY_UNAVAILABLE" and outcome.error.category == "capability"


# ----- grammar selection belongs to analysis and follows each file's type -------------

WEB = {
    "index.html": "<html><body><script>for (let i = 0; i < 3; i++) {}</script>"
                  "<p>for while eval</p></body></html>",
    "styles.css": "body { color: red; } /* for (;;) {} */",
    "app.js": "const items = [1, 2];\nitems.forEach((item) => console.log(item));\n",
    "README.md": "for (;;) {} while (true) {}",
}


def web_definition(extra_tests=()):
    tests = [
        {"id": "html", "type": "has_tag", "name": "Has paragraph", "file": "index.html",
         "parameters": {"tag": "p", "required_count": 1}},
        {"id": "css", "type": "css_uses_property", "name": "Colors", "file": "styles.css",
         "parameters": {"prop": "color", "value": "red"}},
        {"id": "js", "type": "js_uses_feature", "name": "Arrow functions", "file": "app.js",
         "parameters": {"feature": "forEach"}},
        {"id": "loops", "type": "forbidden_keyword", "name": "No loops",
         "parameters": {"forbidden_keywords": ["for_loop", "while_loop"], "custom_ast_grep_rules": []}},
        *extra_tests,
    ]
    return definition(["node"], tests, templates=("webdev", "static_analysis"))


def run_web(files, extra_tests=()):
    submission = Submission("s", "s", "web", {name: SubmissionFile(name, content) for name, content in files.items()})
    return build_pipeline(definition=web_definition(extra_tests)).run(submission).outcome


def scores(outcome):
    return {test.id: test.score for test in outcome.tree.base.tests}


def test_mixed_web_submission_is_parsed_per_file_type():
    """The node runtime does not make HTML, CSS or Markdown JavaScript."""
    outcome = run_web(WEB)
    assert outcome.status == "completed", outcome.error
    assert outcome.language == "node"
    # The inline <script> loop and the loop-like text in CSS/Markdown are never fed to the JS grammar.
    assert scores(outcome) == {"html": 100, "css": 100, "js": 100, "loops": 100}


def test_javascript_source_in_the_same_submission_is_parsed_as_javascript():
    outcome = run_web({**WEB, "app.js": WEB["app.js"] + "for (let i = 0; i < 2; i++) {}\n"})
    assert scores(outcome)["loops"] == 0
    assert "app.js" in outcome.tree.base.tests[3].report and "index.html" not in outcome.tree.base.tests[3].report


def test_targeting_a_document_with_a_source_parser_is_rejected_not_misparsed():
    targeted = {"id": "html-loops", "type": "forbidden_keyword", "name": "No loops in HTML", "file": "index.html",
                "parameters": {"forbidden_keywords": ["for_loop"], "custom_ast_grep_rules": []}}
    outcome = run_web(WEB, [targeted])
    assert outcome.status == "failed" and outcome.error.code == "UNSUPPORTED_FILE_TYPE"


def test_parser_rules_are_owned_by_the_analysis_module():
    from autograder.services import file_selection, structural_analysis
    from autograder.template_library.static_analysis import ForbiddenKeywordTest
    assert not hasattr(file_selection, "SOURCE_GRAMMARS") and not hasattr(file_selection, "LANGUAGE_GRAMMARS")
    assert set(structural_analysis.RUNTIME_GRAMMARS) == set(Language)
    evaluator = ForbiddenKeywordTest()
    assert evaluator.accepts_file("app.mjs", Language.NODE)
    assert not evaluator.accepts_file("index.html", Language.NODE)
    assert not evaluator.accepts_file("main.py", Language.NODE)
    assert structural_analysis.source_grammar("vec.h", Language.CPP) == "cpp"
    assert structural_analysis.source_grammar("vec.h", Language.C) == "c"
