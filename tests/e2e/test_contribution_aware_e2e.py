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
    assert result["submission_files"] == {"main.py": "pass", "helper.py": "pass"}


def test_changed_lines_metadata_preserved_and_scoring_remains_consistent(api_base_url, auth_headers, isolated_api):
    config = create_config(api_base_url, auth_headers)
    file = {"filename": "main.py", "content": "pass\nx = 1", "changed_lines": [1, 2],
        "file_metadata": {"contribution": "opaque-reference", "reviewer": "mentor"}}
    accepted = submit(api_base_url, auth_headers, config, [file],
        evaluation_scope={"scoped_files": ["main.py"]}, metadata={"context": "contribution"})
    result = poll(api_base_url, auth_headers, accepted["id"])
    assert result["outcome"]["score"] == 100
    assert result["submission_metadata"] == {"context": "contribution"}
    # Details intentionally expose source text, while persistence retains caller metadata.
    with sqlite3.connect(isolated_api["database"]) as database:
        stored = json.loads(database.execute("SELECT submission_files FROM submissions WHERE id = ?", (accepted["id"],)).fetchone()[0])
    assert stored["main.py"]["changed_lines"] == [1, 2]
    assert stored["main.py"]["file_metadata"] == file["file_metadata"]
    clean = submit(api_base_url, auth_headers, config, [{"filename": "main.py", "content": "pass\nx = 1"}])
    assert poll(api_base_url, auth_headers, clean["id"])["outcome"]["score"] == result["outcome"]["score"]
