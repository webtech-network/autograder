"""
End-to-end tests for contribution-aware evaluation via the HTTP API.

These tests exercise the full flow:
  1. Create a grading config
  2. Submit code with contribution-aware fields (evaluation_scope, changed_lines, file_metadata)
  3. Poll until completed → verify grading succeeds

Tests cover:
- Submission with evaluation_scope is accepted and graded
- Submission without evaluation_scope is accepted and graded
- Submission with changed_lines and file_metadata is accepted
- Combined contribution-aware submission with baseline_result_tree
"""

import json
import time
import requests
import pytest


def poll_submission(api_base_url, submission_id, auth_headers, timeout=60):
    """Poll until a submission reaches a terminal status."""
    start_time = time.time()
    while time.time() - start_time < timeout:
        response = requests.get(
            f"{api_base_url}/submissions/{submission_id}",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        if data["status"] in ["completed", "failed"]:
            return data
        time.sleep(2)

    response = requests.get(
        f"{api_base_url}/submissions/{submission_id}",
        headers=auth_headers,
    )
    print(f"DEBUG: Timeout reached. State: {json.dumps(response.json(), indent=2)}")
    pytest.fail(f"Submission {submission_id} timed out")


@pytest.fixture
def run_id():
    return int(time.time())


def _create_static_config(api_base_url, auth_headers, config_id, forbidden_imports):
    """Create a static_analysis grading config."""
    config_payload = {
        "external_assignment_id": config_id,
        "template_name": "static_analysis",
        "languages": ["python"],
        "criteria_config": {
            "base": {
                "weight": 100.0,
                "tests": [
                    {
                        "name": f"no_{imp}",
                        "type": "forbidden_import",
                        "forbidden_imports": [imp],
                        "submission_language": "python",
                    }
                    for imp in forbidden_imports
                ],
            }
        },
    }
    response = requests.post(
        f"{api_base_url}/configs",
        json=config_payload,
        headers=auth_headers,
    )
    assert response.status_code in [200, 201]
    return response.json()


def _submit(
    api_base_url,
    auth_headers,
    config_id,
    user_id,
    files,
    evaluation_scope=None,
    baseline_result_tree=None,
):
    """Submit code for grading with optional contribution-aware fields."""
    payload = {
        "external_assignment_id": config_id,
        "external_user_id": user_id,
        "username": f"student-{user_id}",
        "files": files,
    }
    if evaluation_scope is not None:
        payload["evaluation_scope"] = evaluation_scope
    if baseline_result_tree is not None:
        payload["baseline_result_tree"] = baseline_result_tree

    response = requests.post(
        f"{api_base_url}/submissions",
        json=payload,
        headers=auth_headers,
    )
    assert response.status_code in [200, 201], (
        f"Submission failed: {response.status_code} — {response.text}"
    )
    return response.json()


# ==============================================================================
# EVALUATION SCOPE E2E TESTS
# ==============================================================================


class TestEvaluationScopeE2E:
    """E2E tests for evaluation_scope via the HTTP API."""

    def test_submission_with_evaluation_scope_accepted(
        self, api_base_url, auth_headers, run_id
    ):
        """Submit with evaluation_scope → 200, grading completes successfully."""
        config_id = f"scope-accept-{run_id}"
        _create_static_config(api_base_url, auth_headers, config_id, ["os"])

        files = [{"filename": "main.py", "content": "x = 42\nprint(x)"}]
        sub = _submit(
            api_base_url,
            auth_headers,
            config_id,
            f"u-scope-{run_id}",
            files,
            evaluation_scope={"scoped_files": ["main.py"]},
        )
        result = poll_submission(api_base_url, sub["id"], auth_headers)

        assert result["status"] == "completed"
        assert result["final_score"] == 100.0

    def test_submission_without_evaluation_scope_accepted(
        self, api_base_url, auth_headers, run_id
    ):
        """Submit without evaluation_scope → 200, grading completes successfully."""
        config_id = f"scope-none-{run_id}"
        _create_static_config(api_base_url, auth_headers, config_id, ["os"])

        files = [{"filename": "main.py", "content": "x = 42\nprint(x)"}]
        sub = _submit(
            api_base_url,
            auth_headers,
            config_id,
            f"u-noscope-{run_id}",
            files,
        )
        result = poll_submission(api_base_url, sub["id"], auth_headers)

        assert result["status"] == "completed"
        assert result["final_score"] == 100.0

    def test_evaluation_scope_does_not_affect_scoring_for_static_analysis(
        self, api_base_url, auth_headers, run_id
    ):
        """
        Same code with and without evaluation_scope → same score.
        static_analysis tests don't filter by scope, so scores should be identical.
        """
        config_id = f"scope-score-{run_id}"
        _create_static_config(api_base_url, auth_headers, config_id, ["os"])

        files = [{"filename": "main.py", "content": "x = 42\nprint(x)"}]

        # Without scope
        sub1 = _submit(
            api_base_url,
            auth_headers,
            config_id,
            f"u-score1-{run_id}",
            files,
        )
        result1 = poll_submission(api_base_url, sub1["id"], auth_headers)

        # With scope
        sub2 = _submit(
            api_base_url,
            auth_headers,
            config_id,
            f"u-score2-{run_id}",
            files,
            evaluation_scope={"scoped_files": ["main.py"]},
        )
        result2 = poll_submission(api_base_url, sub2["id"], auth_headers)

        assert result1["status"] == "completed"
        assert result2["status"] == "completed"
        assert result1["final_score"] == result2["final_score"]


# ==============================================================================
# CHANGED LINES E2E TESTS
# ==============================================================================


class TestChangedLinesE2E:
    """E2E tests for changed_lines and file_metadata via the HTTP API."""

    def test_submission_with_changed_lines_accepted(
        self, api_base_url, auth_headers, run_id
    ):
        """Submit with changed_lines on files → 200, grading completes."""
        config_id = f"cl-accept-{run_id}"
        _create_static_config(api_base_url, auth_headers, config_id, ["os"])

        files = [
            {
                "filename": "main.py",
                "content": "x = 42\nprint(x)",
                "changed_lines": [1, 2],
            }
        ]
        sub = _submit(
            api_base_url,
            auth_headers,
            config_id,
            f"u-cl-{run_id}",
            files,
        )
        result = poll_submission(api_base_url, sub["id"], auth_headers)

        assert result["status"] == "completed"
        assert result["final_score"] == 100.0

    def test_changed_lines_and_file_metadata_preserved(
        self, api_base_url, auth_headers, run_id
    ):
        """Submit with changed_lines and file_metadata → grading succeeds without errors."""
        config_id = f"cl-meta-{run_id}"
        _create_static_config(api_base_url, auth_headers, config_id, ["os"])

        files = [
            {
                "filename": "main.py",
                "content": "x = 42\nprint(x)",
                "changed_lines": [1],
                "file_metadata": {
                    "change_status": "modified",
                    "provider": "github",
                    "stats": {"additions": 1, "deletions": 0},
                },
            }
        ]
        sub = _submit(
            api_base_url,
            auth_headers,
            config_id,
            f"u-clm-{run_id}",
            files,
        )
        result = poll_submission(api_base_url, sub["id"], auth_headers)

        assert result["status"] == "completed"
        assert result["final_score"] == 100.0

    def test_submission_without_changed_lines_accepted(
        self, api_base_url, auth_headers, run_id
    ):
        """Submit without changed_lines → 200, grading completes (backward compatible)."""
        config_id = f"cl-none-{run_id}"
        _create_static_config(api_base_url, auth_headers, config_id, ["os"])

        files = [{"filename": "main.py", "content": "x = 42"}]
        sub = _submit(
            api_base_url,
            auth_headers,
            config_id,
            f"u-clnone-{run_id}",
            files,
        )
        result = poll_submission(api_base_url, sub["id"], auth_headers)

        assert result["status"] == "completed"


# ==============================================================================
# COMBINED CONTRIBUTION-AWARE E2E TESTS
# ==============================================================================


class TestCombinedContributionAwareE2E:
    """E2E tests combining all contribution-aware features."""

    def test_full_contribution_aware_submission(
        self, api_base_url, auth_headers, run_id
    ):
        """
        Submit with evaluation_scope + changed_lines + file_metadata + baseline_result_tree
        → everything works together, comparison present in response.
        """
        config_id = f"combined-{run_id}"
        _create_static_config(api_base_url, auth_headers, config_id, ["os"])

        # First submission (baseline) — violation code
        baseline_files = [
            {
                "filename": "main.py",
                "content": "import os\nprint(os.getcwd())",
                "changed_lines": [1, 2],
                "file_metadata": {"change_status": "added"},
            }
        ]
        sub1 = _submit(
            api_base_url,
            auth_headers,
            config_id,
            f"u-comb-base-{run_id}",
            baseline_files,
            evaluation_scope={"scoped_files": ["main.py"]},
        )
        result1 = poll_submission(api_base_url, sub1["id"], auth_headers)
        assert result1["status"] == "completed"
        assert result1["final_score"] < 100.0
        assert result1["comparison"] is None  # No baseline → no comparison
        baseline_tree = result1["result_tree"]

        # Second submission (head) — clean code with baseline
        head_files = [
            {
                "filename": "main.py",
                "content": "x = 42\nprint(x)",
                "changed_lines": [1, 2],
                "file_metadata": {"change_status": "modified"},
            }
        ]
        sub2 = _submit(
            api_base_url,
            auth_headers,
            config_id,
            f"u-comb-head-{run_id}",
            head_files,
            evaluation_scope={"scoped_files": ["main.py"]},
            baseline_result_tree=baseline_tree,
        )
        result2 = poll_submission(api_base_url, sub2["id"], auth_headers)

        assert result2["status"] == "completed"
        assert result2["final_score"] == 100.0

        # Comparison should show improvement
        comparison = result2["comparison"]
        assert comparison is not None
        assert comparison["score_delta"] > 0
        assert comparison["improved"] is True

        # score_vector should also be present
        assert result2["score_vector"] is not None

    def test_multi_file_with_scope_and_metadata(
        self, api_base_url, auth_headers, run_id
    ):
        """
        Multi-file submission with evaluation_scope scoping to a subset.
        Verify grading completes successfully.
        """
        config_id = f"multi-scope-{run_id}"
        _create_static_config(api_base_url, auth_headers, config_id, ["os"])

        files = [
            {
                "filename": "main.py",
                "content": "x = 42",
                "changed_lines": [1],
                "file_metadata": {"change_status": "modified"},
            },
            {
                "filename": "utils.py",
                "content": "def helper(): return 1",
                "changed_lines": None,
                "file_metadata": {"change_status": "unchanged"},
            },
        ]
        sub = _submit(
            api_base_url,
            auth_headers,
            config_id,
            f"u-multi-{run_id}",
            files,
            evaluation_scope={"scoped_files": ["main.py"]},
        )
        result = poll_submission(api_base_url, sub["id"], auth_headers)

        assert result["status"] == "completed"
        assert result["final_score"] == 100.0
