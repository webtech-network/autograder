"""Submission failures explain themselves to the student; infrastructure stays opaque (ONB-02).

These run the public pipeline with a fake execution session at the host seam;
tests/integration/test_submission_explanations_docker.py runs the same failures
in real Java and C sandboxes.
"""
import json
from unittest.mock import Mock

import pytest
from pydantic import ValidationError

from autograder import DefinitionValidationError, build_pipeline, compile_definition
from autograder.models.capabilities import FixtureNotFound, HostCapabilities
from autograder.models.contracts.outcome import MAX_REPORT_BYTES, OutcomeError, text_bytes, validate_outcome
from autograder.models.dataclass.submission import EvaluationScope, Submission, SubmissionFile
from autograder.models.evaluation_error import EvaluationError
from autograder.models.language import Language
from autograder.models.process import SandboxExhausted
from tests.process_results import exited, not_started, timed_out

COMPILE_ERROR = "Main.java:3: error: ';' expected\n        int x = 1\n                 ^\n1 error\n"
SUBMITTED = {"Main.java": SubmissionFile("Main.java", "class Main {}")}


def definition(*, setup=None, required=("Main.java",), languages=("java",), tests=None):
    java = {"required_files": list(required)}
    if setup is not None:
        java["setup_commands"] = setup
    return {"schema_version": "1.0", "templates": ["input_output"], "languages": list(languages),
            "preparation": {"languages": {"java": java}},
            "criteria": {"base": {"weight": 100, "tests": tests or [
                {"id": "runs", "type": "dont_fail", "name": "Runs", "parameters": {"program_command": "java Main"}}]}}}


def compile_step(**extra):
    return [{"name": "compile", "command": "javac Main.java", **extra}]


def session(*results):
    fake = Mock()
    fake.run_process.side_effect = list(results)
    return fake


def run(value, *, files=None, language=Language.JAVA, locale="en", execution=None, fixtures=None, scope=None):
    capabilities = HostCapabilities(execution=(lambda _language, _budget: execution) if execution else None, fixtures=fixtures)
    outcome = build_pipeline(definition=value, capabilities=capabilities).run(Submission(
        "student", 1, 1, SUBMITTED if files is None else files, language=language, locale=locale,
        evaluation_scope=scope)).outcome
    assert outcome.status == "failed" and outcome.score is None and outcome.tree is None
    assert validate_outcome(outcome.model_dump(mode="json")) == outcome
    return outcome.error


# --- the student-visible explanation, in both locales -------------------------------------------

@pytest.mark.parametrize("locale,expected", [
    ("en", "The setup step 'compile' failed with exit code 1, so the submission could not be graded."),
    ("pt-br", "A etapa de preparação 'compile' falhou com código de saída 1, então a submissão não pôde ser avaliada."),
])
def test_failing_setup_step_is_named_with_its_output(locale, expected):
    error = run(definition(setup=compile_step()), locale=locale,
                execution=session(exited(stderr=COMPILE_ERROR, code=1)))
    assert (error.code, error.category, error.retryable) == ("PREPARATION_FAILED", "submission", False)
    assert error.message == expected
    assert error.output == COMPILE_ERROR


def test_output_keeps_both_streams_and_is_excerpted_to_the_report_bound():
    flood = "Main.java:1: error: cannot find symbol\n" * 20_000
    error = run(definition(setup=compile_step()), execution=session(exited("javac 21", flood, code=2)))
    assert "exit code 2" in error.message
    assert text_bytes(error.output) <= MAX_REPORT_BYTES
    assert error.output.startswith("javac 21\nMain.java:1: error: cannot find symbol")
    assert error.output.endswith("cannot find symbol\n")
    assert f"of {len('javac 21') + 1 + len(flood)} bytes omitted" in error.output


@pytest.mark.parametrize("locale,expected", [
    ("en", "The setup step 'compile' did not finish within 30 seconds, so the submission could not be graded."),
    ("pt-br", "A etapa de preparação 'compile' não terminou em 30 segundos, então a submissão não pôde ser avaliada."),
])
def test_setup_timeout_is_explained(locale, expected):
    error = run(definition(setup=compile_step()), locale=locale, execution=session(timed_out(stderr="partial")))
    assert (error.code, error.message, error.output) == ("PREPARATION_FAILED", expected, "partial")


def test_setup_exhaustion_names_the_step_without_output():
    error = run(definition(setup=compile_step()), execution=session(SandboxExhausted("limit")))
    assert error.code == "PREPARATION_FAILED"
    assert error.message == ("The setup step 'compile' exceeded the sandbox's memory or process limit, "
                             "so the submission could not be graded.")
    assert error.output is None


@pytest.mark.parametrize("locale,expected", [
    ("en", "Required file not found: Main.java. Submit it with exactly this name and path."),
    ("pt-br", "Arquivo obrigatório não encontrado: Main.java. Envie-o exatamente com este nome e caminho."),
])
def test_missing_required_file_is_named(locale, expected):
    acquire = Mock(side_effect=AssertionError("must not acquire"))
    error = run(definition(setup=compile_step()), files={"main.java": SubmissionFile("main.java", "")},
                locale=locale, execution=acquire)
    assert (error.code, error.category, error.message) == ("REQUIRED_FILE_MISSING", "submission", expected)
    assert error.output is None and "output" not in error.model_dump(mode="json")


def test_missing_criterion_target_names_the_criterion_and_file():
    tests = [{"id": "words", "type": "forbidden_keyword", "name": "No while", "file": "Util.java",
              "parameters": {"forbidden_keywords": ["while_loop"]}}]
    value = definition(tests=tests)
    value["templates"] = ["static_analysis"]
    error = run(value, locale="pt-br")
    assert error.code == "REQUIRED_FILE_MISSING"
    assert error.message == ("O critério 'No while' avalia Util.java, que não foi enviado. "
                             "Envie-o exatamente com este nome e caminho.")


def test_target_outside_the_evaluation_scope_is_named():
    tests = [{"id": "words", "type": "forbidden_keyword", "name": "No while", "file": "Main.java",
              "parameters": {"forbidden_keywords": ["while_loop"]}}]
    value = definition(tests=tests, required=())
    value["templates"] = ["static_analysis"]
    error = run(value, files={**SUBMITTED, "Other.java": SubmissionFile("Other.java", "")},
                scope=EvaluationScope(["Other.java"]))
    assert error.code == "FILE_TARGET_CONFLICT"
    assert error.message == ("The criterion 'No while' assesses Main.java, which is outside the files "
                             "selected for this evaluation.")


def test_ambiguous_single_file_target_counts_matches_without_echoing_student_names():
    tests = [{"id": "page", "type": "has_tag", "name": "Has a title",
              "parameters": {"tag": "title", "required_count": 1}}]
    value = {"schema_version": "1.0", "templates": ["webdev"], "languages": ["python"],
             "criteria": {"base": {"weight": 100, "tests": tests}}}
    student_names = {name: SubmissionFile(name, "<p>") for name in ("a-secret-name.html", "b.html")}
    error = run(value, files=student_names, language=Language.PYTHON)
    assert error.code == "AMBIGUOUS_FILE_TARGET"
    assert error.message.startswith("The criterion 'Has a title' assesses at most 1 file(s), but 2 submitted files match.")
    assert "a-secret-name" not in error.message


@pytest.mark.parametrize("language,locale,code,expected", [
    (None, "en", "LANGUAGE_REQUIRED", "This assignment accepts several languages. Select one of: java, c."),
    (None, "pt-br", "LANGUAGE_REQUIRED", "Esta atividade aceita várias linguagens. Selecione uma destas: java, c."),
    (Language.PYTHON, "en", "LANGUAGE_NOT_ALLOWED",
     "The language 'python' is not accepted by this assignment. Use one of: java, c."),
    (Language.PYTHON, "pt-br", "LANGUAGE_NOT_ALLOWED",
     "A linguagem 'python' não é aceita por esta atividade. Use uma destas: java, c."),
])
def test_language_failures_name_the_allowed_set(language, locale, code, expected):
    error = run(definition(languages=("java", "c")), language=language, locale=locale)
    assert (error.code, error.category, error.message) == (code, "submission", expected)


def test_an_arbitrary_language_string_is_not_echoed():
    error = run(definition(), language="x" * 10_000)
    assert error.code == "LANGUAGE_NOT_ALLOWED"
    assert error.message == "The language '?' is not accepted by this assignment. Use one of: java."


# --- the author's opt-out ------------------------------------------------------------------------

def test_private_output_hides_the_step_output_but_still_names_the_step():
    error = run(definition(setup=compile_step(private_output=True)),
                execution=session(exited(stderr="HiddenHarness.java:9: secret assertion", code=1)))
    assert error.message.startswith("The setup step 'compile' failed with exit code 1")
    assert error.output is None
    assert "HiddenHarness" not in json.dumps(error.model_dump(mode="json"))


@pytest.mark.parametrize("value", ["true", 1, None, [], {}])
def test_private_output_is_validated_at_compile_time(value):
    with pytest.raises(DefinitionValidationError) as raised:
        compile_definition(definition(setup=compile_step(private_output=value)))
    assert any(error["path"][-1] == "private_output" for error in raised.value.errors())


def test_the_opt_out_keeps_existing_definition_hashes():
    plain = compile_definition(definition(setup=compile_step()))
    explicit_default = compile_definition(definition(setup=compile_step(private_output=False)))
    private = compile_definition(definition(setup=compile_step(private_output=True)))
    # Pinned from the base branch: definitions written before the field keep their identity.
    assert plain.definition_hash == "6100775ee56085bc7de12727ab3f88a69a64f8b7ef186eec35d8b693cfd3ce2b"
    assert explicit_default.definition_hash == plain.definition_hash
    assert "private_output" not in json.dumps(plain.definition.model_dump(mode="json"))
    assert private.definition_hash != plain.definition_hash
    assert private.definition.preparation.languages["java"].setup_commands[0].private_output is True


# --- infrastructure stays byte-for-byte opaque ---------------------------------------------------

def _wire(error):
    data = error.model_dump(mode="json")
    data.pop("correlation_id")
    return data


@pytest.mark.parametrize("make,expected", [
    (lambda: {"execution": session(not_started("javac"))},
     {"code": "PREPARATION_ERROR", "message": "A setup command could not be started.",
      "category": "capability", "retryable": False}),
    (lambda: {"execution": session(RuntimeError("docker: /var/lib/secret-path exploded"))},
     {"code": "PREPARATION_ERROR", "message": "Assignment preparation could not complete.",
      "category": "capability", "retryable": True}),
    (lambda: {"execution": session(exited()), "fixtures": Mock(side_effect=FixtureNotFound("bucket/key"))},
     {"code": "PREPARATION_ERROR", "message": "Assignment preparation could not complete.",
      "category": "capability", "retryable": False}),
    (lambda: {"execution": None},
     {"code": "CAPABILITY_UNAVAILABLE", "message": "The execution environment is unavailable.",
      "category": "capability", "retryable": False}),
])
@pytest.mark.parametrize("locale", ["en", "pt-br"])
def test_capability_failures_are_unchanged_in_every_locale(make, expected, locale):
    value = definition(setup=compile_step())
    capabilities = make()
    if "fixtures" in capabilities:
        value["preparation"]["fixtures"] = [{"reference": "bucket/key", "path": "data.bin"}]
    error = run(value, locale=locale, **capabilities)
    assert _wire(error) == expected


def _ai_definition():
    return {"schema_version": "1.0", "templates": ["static_analysis"], "languages": ["java"],
            "criteria": {"base": {"weight": 100, "tests": [{"id": "sort", "type": "ai_sorting_algorithm",
                                                             "name": "Sort", "parameters": {"algorithm_name": "Merge Sort"}}]}}}


def _provider(error):
    provider = Mock()
    provider.assess.side_effect = error
    return provider


@pytest.mark.parametrize("make,expected", [
    # Assessment-time seam: the sandbox transport fails while the evaluator runs.
    (lambda: (definition(), HostCapabilities(execution=lambda _language, _budget: session(RuntimeError("/var/lib/docker secret")))),
     {"code": "SANDBOX_ERROR", "message": "The execution environment could not complete evaluation.",
      "category": "capability", "retryable": True}),
    # The host returns something that is not a process result: an unexpected engine failure.
    (lambda: (definition(), HostCapabilities(execution=lambda _language, _budget: Mock(**{"run_process.return_value": "junk"}))),
     {"code": "EXECUTION_ERROR", "message": "The grading execution could not complete.",
      "category": "internal", "retryable": False}),
    (lambda: (_ai_definition(), HostCapabilities()),
     {"code": "PROVIDER_UNAVAILABLE", "message": "The assessment provider is unavailable.",
      "category": "provider", "retryable": False}),
    (lambda: (_ai_definition(), HostCapabilities(ai=_provider(RuntimeError("upstream said: sk-secret")))),
     {"code": "PROVIDER_ERROR", "message": "The assessment provider could not complete evaluation.",
      "category": "provider", "retryable": True}),
])
@pytest.mark.parametrize("locale", ["en", "pt-br"])
def test_sandbox_provider_and_internal_failures_are_unchanged_in_every_locale(make, expected, locale):
    value, capabilities = make()
    outcome = build_pipeline(definition=value, capabilities=capabilities).run(
        Submission("student", 1, 1, SUBMITTED, language=Language.JAVA, locale=locale)).outcome
    assert outcome.status == "failed"
    assert _wire(outcome.error) == expected


# --- the wire contract ---------------------------------------------------------------------------

def _error(**values):
    return {"code": "PREPARATION_FAILED", "message": "m", "category": "submission", "retryable": False,
            "correlation_id": "e", **values}


def test_output_is_only_for_submission_errors():
    with pytest.raises(ValidationError, match="Only submission errors carry output"):
        OutcomeError(**_error(code="SANDBOX_ERROR", category="capability", output="x"))
    with pytest.raises(ValueError, match="Only submission failures"):
        EvaluationError("SANDBOX_ERROR", "m", "capability", output="x")
    with pytest.raises(ValueError, match="Only submission failures"):
        EvaluationError("PROVIDER_ERROR", "m", "provider", explanation=("preflight.error.language_required", {}))


def test_attested_output_above_the_bound_is_rejected_never_truncated():
    assert OutcomeError(**_error(output="x" * MAX_REPORT_BYTES)).output == "x" * MAX_REPORT_BYTES
    with pytest.raises(ValidationError) as raised:
        OutcomeError(**_error(output="x" * (MAX_REPORT_BYTES + 1)))
    assert raised.value.errors()[0]["type"] == "text_too_large"


def test_errors_without_output_serialize_exactly_as_before():
    error = OutcomeError(**_error())
    assert list(error.model_dump(mode="json")) == ["code", "message", "category", "retryable", "correlation_id"]
    assert "output" not in error.model_dump_json()
    assert OutcomeError(**_error(output=None)) == error
