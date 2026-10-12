"""Assessment inputs are deterministic and parsing stays with static assessment."""
from unittest.mock import call, MagicMock, patch

import pytest

from autograder import build_pipeline
from autograder.models.capabilities import HostCapabilities
from autograder.models.criteria_tree import CategoryNode, CriteriaTree, TestNode as Criterion
from autograder.models.dataclass.submission import EvaluationScope, Submission, SubmissionFile
from autograder.models.evaluation_error import EvaluationError
from autograder.services.file_selection import select_files
from autograder.services.grader.grader_service import GraderService
from autograder.services.structural_analysis import StructuralAnalysisCache
from autograder.steps.ai_batch_step import AiBatchStep
from autograder.template_library.static_analysis import AiSortingAlgorithmTest, ForbiddenKeywordTest
from autograder.template_library.input_output import DontFailTest
from autograder.template_library.api_testing import HealthCheckTest
from autograder.template_library.web_dev.html_tests import HasTag
from autograder.template_library.web_dev.css_tests import CountUnusedCssClasses
from autograder.template_library.web_dev.structure_tests import CheckProjectStructure
from sandbox_manager.models.sandbox_models import CommandResponse, Language


def files(*pairs):
    """Build submission file objects without changing insertion order."""
    return {name: SubmissionFile(name, content) for name, content in pairs}


def criterion(function, **kwargs):
    """Build an identified criterion for direct assessment tests."""
    return Criterion(name="Check", test_function=function, criterion_id="check", **kwargs)


@pytest.mark.parametrize("reverse", [False, True])
def test_html_input_ignores_context_and_upload_order(reverse):
    """An HTML criterion selects its source even when README arrives first."""
    values = [("README.md", "<title>context</title>"), ("index.html", "<main>Hello</main>")]
    submitted = files(*(reversed(values) if reverse else values))
    tree = CriteriaTree(base=CategoryNode("base", 100, tests=[criterion(HasTag(), parameters={"tag": "main", "required_count": 1})]))
    result = GraderService().grade_from_tree(tree, submitted)
    assert result.calculate_final_score() == 100
    assert select_files(tree.base.tests[0], submitted)[0].filename == "index.html"


@pytest.mark.parametrize("target,code", [
    (None, "AMBIGUOUS_FILE_TARGET"),
    (["missing.html"], "REQUIRED_FILE_MISSING"),
    (["README.md"], "UNSUPPORTED_FILE_TYPE"),
])
def test_single_file_contract_fails_before_assessment(target, code):
    """Ambiguous, missing and wrong-type targets are distinct required failures."""
    submitted = files(("a.html", "<main/>"), ("b.html", "<main/>"), ("README.md", "docs"))
    with pytest.raises(EvaluationError) as error:
        select_files(criterion(HasTag(), file_target=target), submitted)
    assert error.value.code == code


def test_explicit_target_disambiguates_html_and_conflicts_with_scope():
    """Explicit files resolve ambiguity and cannot escape the caller scope."""
    submitted = files(("a.html", "<main/>"), ("b.html", "<main/>"))
    test = criterion(HasTag(), file_target=["b.html"])
    assert [f.filename for f in select_files(test, submitted)] == ["b.html"]
    with pytest.raises(EvaluationError) as error:
        select_files(test, submitted, EvaluationScope(scoped_files=["a.html"]))
    assert error.value.code == "FILE_TARGET_CONFLICT"


def test_scoped_source_selection_retains_context_for_execution_and_project_checks():
    """Scope limits source assessment without removing project dependencies."""
    submitted = files(("main.py", "x=1"), ("helper.py", "x=2"), ("README.md", "docs"))
    scope = EvaluationScope(scoped_files=["main.py"])
    assert [f.filename for f in select_files(criterion(ForbiddenKeywordTest()), submitted, scope, Language.PYTHON)] == ["main.py"]
    for function in (DontFailTest(), CheckProjectStructure()):
        assert {f.filename for f in select_files(criterion(function), submitted, scope)} == set(submitted)
    assert select_files(criterion(HealthCheckTest()), submitted, scope) == []


def test_named_multi_file_inputs_are_required_and_respect_explicit_targets():
    """Multi-file checks require every named input and consistent targets."""
    submitted = files(("index.html", ""), ("site.css", ""), ("README.md", "docs"))
    test = criterion(CountUnusedCssClasses(), parameters={"html_file": "index.html", "css_file": "site.css"})
    assert [f.filename for f in select_files(test, submitted)] == ["index.html", "site.css"]
    test.file_target = ["index.html"]
    with pytest.raises(EvaluationError) as error:
        select_files(test, submitted)
    assert error.value.code == "FILE_TARGET_CONFLICT"
    test.file_target = None
    del submitted["site.css"]
    with pytest.raises(EvaluationError) as error:
        select_files(test, submitted)
    assert error.value.code == "REQUIRED_FILE_MISSING"


def test_ai_and_ordinary_assessment_share_scoped_selection():
    """AI batching follows the same scope and conflict policy as ordinary grading."""
    submitted = files(("b.py", "b=1"), ("a.py", "a=1"), ("README.md", "docs"))
    scope = EvaluationScope(scoped_files=["a.py"])
    test = criterion(AiSortingAlgorithmTest(), parameters={"algorithm_name": "merge sort"})
    tree = CriteriaTree(base=CategoryNode("base", 100, tests=[test]))
    entries = AiBatchStep()._collect_ai_tests(tree, submitted, scope, Language.PYTHON)  # pylint: disable=protected-access
    assert entries[0][1] == select_files(test, submitted, scope, Language.PYTHON)
    assert [f.filename for f in entries[0][1]] == ["a.py"]
    test.file_target = ["b.py"]
    with pytest.raises(EvaluationError) as error:
        AiBatchStep()._collect_ai_tests(tree, submitted, scope, Language.PYTHON)  # pylint: disable=protected-access
    assert error.value.code == "FILE_TARGET_CONFLICT"


def static_pipeline(*tests):
    """Build a real static assessment pipeline from the public definition."""
    return build_pipeline(definition={"schema_version": "1.0", "templates": ["static_analysis"],
        "languages": ["python"], "criteria": {"base": {"weight": 100, "tests": list(tests)}}})


def keyword(criterion_id="keyword", **kwargs):
    """Build one structural criterion using a supported rule."""
    return {"id": criterion_id, "type": "forbidden_keyword", "name": "For loops",
        "parameters": {"forbidden_keywords": ["for_loop"]}, **kwargs}


def submission(submitted, scope=None):
    """Build a submission whose identifiers are opaque to grading."""
    return Submission(username="student", user_id="opaque", assignment_id="opaque",
                      submission_files=submitted, language=Language.PYTHON, evaluation_scope=scope)


@pytest.mark.parametrize("scope", [None, EvaluationScope(scoped_files=["main.py"])])
def test_python_plus_readme_and_unparsed_context_complete(scope):
    """Documents and out-of-scope sources cannot cause missing AST failures."""
    submitted = files(("main.py", "x = 1"), ("README.md", "for loops are forbidden"))
    if scope is not None:
        submitted.update(files(("helper.py", "for i in range(3): pass")))
    execution = static_pipeline(keyword()).run(submission(submitted, scope))
    assert execution.outcome.status == "completed"
    assert execution.outcome.score == 100


def test_cache_is_content_and_grammar_specific_and_execution_local():
    """Criteria share parses only within the same execution and grammar."""
    with patch("autograder.services.structural_analysis.SgRoot") as parser:
        parser.return_value.root.return_value.find_all.return_value = []
        pipeline = static_pipeline(keyword("first"), keyword("second"))
        submitted = files(("main.py", "x = 1"), ("README.md", "context"))
        assert pipeline.run(submission(submitted)).outcome.status == "completed"
        assert parser.call_args_list == [call("x = 1", "python")]
        assert pipeline.run(submission(submitted)).outcome.status == "completed"
        assert parser.call_count == 2
        cache = StructuralAnalysisCache()
        cache.root_for(SubmissionFile("same.py", "x = 1"))
        cache.root_for(SubmissionFile("other.py", "x = 1"))
        cache.root_for(SubmissionFile("same.py", "x = 2"))
        cache.root_for(SubmissionFile("same.js", "x = 1"))
        assert parser.call_count == 5
        assert parser.call_args.args == ("x = 1", "javascript")


def test_unneeded_ast_is_never_created_and_missing_target_has_no_grade():
    """Nonstructural criteria do no parsing and required targets never yield a grade."""
    with patch("autograder.services.structural_analysis.SgRoot", side_effect=AssertionError("Unexpected parse")):
        pipeline = static_pipeline({"id": "imports", "type": "forbidden_import", "name": "Imports", "parameters": {"forbidden_imports": ["os"]}})
        assert pipeline.run(submission(files(("main.py", "x=1"), ("README.md", "import os")))).outcome.score == 100
        failed = static_pipeline(keyword(file="missing.py")).run(submission(files(("main.py", "x=1")))).outcome
        assert failed.status == "failed"
        assert failed.score is None and failed.tree is None
        assert failed.error.code == "REQUIRED_FILE_MISSING"


def test_html_and_io_pipelines_do_no_structural_parsing():
    """HTML and I/O execution never request AST roots from their context files."""
    with patch("autograder.services.structural_analysis.SgRoot", side_effect=AssertionError("Unexpected parse")) as parser:
        html = build_pipeline(definition={"schema_version": "1.0", "templates": ["webdev"],
            "languages": ["python"], "criteria": {"base": {"weight": 100, "tests": [{
                "id": "html", "type": "has_tag", "name": "Main", "parameters": {"tag": "main", "required_count": 1}}]}}})
        assert html.run(submission(files(("index.html", "<main/>"), ("README.md", "docs")))).outcome.score == 100
        session = MagicMock()
        session.run_commands.return_value = CommandResponse(stdout="", stderr="", exit_code=0, execution_time=0)
        io = build_pipeline(definition={"schema_version": "1.0", "templates": ["input_output"],
            "languages": ["python"], "criteria": {"base": {"weight": 100, "tests": [{
                "id": "io", "type": "dont_fail", "name": "Run", "parameters": {"program_command": "python3 main.py"}}]}}},
            capabilities=HostCapabilities(execution=lambda _: session))
        submitted = files(("main.py", "import helper"), ("helper.py", "x=1"), ("README.md", "docs"))
        assert io.run(submission(submitted, EvaluationScope(scoped_files=["main.py"]))).outcome.score == 100
        session.prepare_workdir.assert_called_once_with(submitted)
        session.close.assert_called_once()
        parser.assert_not_called()


def test_ai_batch_assesses_scoped_sources_with_other_files_as_context():
    """The prompt names assessed files while the provider retains complete context."""
    provider = MagicMock()
    from autograder.models.dataclass.test_result import TestResult  # pylint: disable=import-outside-toplevel
    provider.run.return_value = {"algorithm": TestResult("algorithm", 100, "Correct")}
    pipeline = build_pipeline(definition={"schema_version": "1.0", "templates": ["static_analysis"],
        "languages": ["python"], "criteria": {"base": {"weight": 100, "tests": [{
            "id": "algorithm", "type": "ai_sorting_algorithm", "name": "Sorting",
            "parameters": {"algorithm_name": "merge sort"}}]}}}, capabilities=HostCapabilities(ai=provider))
    submitted = files(("main.py", "x=1"), ("helper.py", "x=2"), ("README.md", "docs"))
    outcome = pipeline.run(submission(submitted, EvaluationScope(scoped_files=["main.py"]))).outcome
    assert outcome.status == "completed" and outcome.score == 100
    inputs, context, locale = provider.run.call_args.args
    assert len(inputs) == 1
    assert "Focus only on these files: main.py." in inputs[0].prompt
    assert "helper.py" not in inputs[0].prompt and "README.md" not in inputs[0].prompt
    assert context == {name: file.content for name, file in submitted.items()}
    assert locale == "en"
