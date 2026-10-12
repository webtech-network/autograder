"""Real HTTP hydration and persistence of caller-owned contribution context."""
import json
import sqlite3
import pytest

from tests.e2e.contracts import create_config, poll, submit


@pytest.mark.parametrize("scope", [None, {"scoped_files": ["main.py"]}])
def test_evaluation_scope_and_context_are_accepted(api_base_url, auth_headers, scope):
    config = create_config(api_base_url, auth_headers)
    extra = {} if scope is None else {"evaluation_scope": scope}
    accepted = submit(api_base_url, auth_headers, config,
        [{"filename": "main.py", "content": "pass"}, {"filename": "helper.py", "content": "pass"}], **extra)
    result = poll(api_base_url, auth_headers, accepted["id"])
    assert result["outcome"]["score"] == 100
    assert {name: file["content"] for name, file in result["submission_files"].items()} == {"main.py": "pass", "helper.py": "pass"}


def test_changed_lines_metadata_preserved_and_scoring_remains_consistent(api_base_url, auth_headers, isolated_api):
    config = create_config(api_base_url, auth_headers)
    file = {"filename": "main.py", "content": "pass\nx = 1", "changed_lines": [1, 2],
        "file_metadata": {"contribution": "opaque-reference", "reviewer": "mentor"}}
    accepted = submit(api_base_url, auth_headers, config, [file],
        evaluation_scope={"scoped_files": ["main.py"]}, metadata={"context": "contribution"})
    result = poll(api_base_url, auth_headers, accepted["id"])
    assert result["outcome"]["score"] == 100
    assert result["submission_metadata"] == {"context": "contribution"}
    assert result["submission_files"]["main.py"]["changed_lines"] == [1, 2]
    assert result["submission_files"]["main.py"]["file_metadata"] == file["file_metadata"]
    assert result["evaluation_scope"] == {"scoped_files": ["main.py"]}
    with sqlite3.connect(isolated_api["database"]) as database:
        stored = json.loads(database.execute("SELECT submission_files FROM submissions WHERE id = ?", (accepted["id"],)).fetchone()[0])
    assert stored["main.py"]["changed_lines"] == [1, 2]
    assert stored["main.py"]["file_metadata"] == file["file_metadata"]
    clean = submit(api_base_url, auth_headers, config, [{"filename": "main.py", "content": "pass\nx = 1"}])
    assert poll(api_base_url, auth_headers, clean["id"])["outcome"]["score"] == result["outcome"]["score"]


@pytest.mark.parametrize("scope", [None, {"scoped_files": ["main.py"]}])
def test_structural_assessment_keeps_documents_and_unscoped_sources_as_context(api_base_url, auth_headers, scope):
    """Actual HTTP grading parses only the Python sources selected for assessment."""
    from tests.e2e.contracts import definition  # pylint: disable=import-outside-toplevel
    value = definition(tests=[{"id": "no-loops", "name": "No loops", "type": "forbidden_keyword",
                              "parameters": {"forbidden_keywords": ["for_loop"]}}])
    config = create_config(api_base_url, auth_headers, value)
    submitted = [{"filename": "README.md", "content": "for loops are forbidden"},
                 {"filename": "main.py", "content": "x = 1"}]
    if scope is not None:
        submitted.append({"filename": "helper.py", "content": "for i in range(3): pass"})
    extra = {} if scope is None else {"evaluation_scope": scope}
    accepted = submit(api_base_url, auth_headers, config, submitted, **extra)
    result = poll(api_base_url, auth_headers, accepted["id"])
    assert result["outcome"]["status"] == "completed"
    assert result["outcome"]["score"] == 100
    assert set(result["submission_files"]) == {file["filename"] for file in submitted}
