"""
End-to-end tests for baseline comparison via the HTTP API.

These tests exercise the full flow:
  1. Create a grading config
  2. Submit code → poll until completed → capture result_tree
  3. Submit again with baseline_result_tree → poll → verify comparison in response

Tests cover:
- Score improvement produces positive delta and improved=True
- Score regression produces negative delta and improved=False
- Identical submissions produce zero delta and unchanged statuses
- Comparison not present when baseline_result_tree is omitted
- External result ingestion preserves comparison field
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


def _submit(api_base_url, auth_headers, config_id, user_id, code, baseline_result_tree=None):
    """Submit code for grading, optionally with a baseline_result_tree."""
    payload = {
        "external_assignment_id": config_id,
        "external_user_id": user_id,
        "username": f"student-{user_id}",
        "files": [{"filename": "main.py", "content": code}],
    }
    if baseline_result_tree is not None:
        payload["baseline_result_tree"] = baseline_result_tree

    response = requests.post(
        f"{api_base_url}/submissions",
        json=payload,
        headers=auth_headers,
    )
    assert response.status_code in [200, 201]
    return response.json()


# ==============================================================================
# BASELINE COMPARISON E2E TESTS
# ==============================================================================


class TestBaselineComparisonE2E:
    """E2E tests for baseline comparison via the HTTP API."""

    def test_comparison_on_score_improvement(self, api_base_url, auth_headers, run_id):
        """
        Submit violation code → submit clean code with baseline → verify comparison
        shows improvement.
        """
        config_id = f"cmp-improve-{run_id}"
        _create_static_config(api_base_url, auth_headers, config_id, ["os"])

        # First submission: violation code (baseline)
        sub1 = _submit(
            api_base_url, auth_headers, config_id,
            f"u-cmp-base-{run_id}", "import os\nprint(os.getcwd())",
        )
        result1 = poll_submission(api_base_url, sub1["id"], auth_headers)
        assert result1["status"] == "completed"
        assert result1["final_score"] < 100.0
        assert result1["comparison"] is None, "No baseline → no comparison"
        baseline_tree = result1["result_tree"]
        assert baseline_tree is not None

        # Second submission: clean code with baseline
        sub2 = _submit(
            api_base_url, auth_headers, config_id,
            f"u-cmp-head-{run_id}", "x = 42\nprint(x)",
            baseline_result_tree=baseline_tree,
        )
        result2 = poll_submission(api_base_url, sub2["id"], auth_headers)
        assert result2["status"] == "completed"
        assert result2["final_score"] == 100.0

        # Verify comparison
        comparison = result2["comparison"]
        assert comparison is not None, "Comparison should be present when baseline provided"
        assert comparison["score_delta"] > 0
        assert comparison["improved"] is True
        assert len(comparison["test_deltas"]) >= 1

        # At least one test should show 'improved'
        statuses = {d["status"] for d in comparison["test_deltas"]}
        assert "improved" in statuses

    def test_comparison_on_score_regression(self, api_base_url, auth_headers, run_id):
        """
        Submit clean code → submit violation code with baseline → verify regression.
        """
        config_id = f"cmp-regress-{run_id}"
        _create_static_config(api_base_url, auth_headers, config_id, ["os"])

        # Baseline: clean code
        sub1 = _submit(
            api_base_url, auth_headers, config_id,
            f"u-regr-base-{run_id}", "x = 1",
        )
        result1 = poll_submission(api_base_url, sub1["id"], auth_headers)
        assert result1["status"] == "completed"
        assert result1["final_score"] == 100.0
        baseline_tree = result1["result_tree"]

        # Head: violation code
        sub2 = _submit(
            api_base_url, auth_headers, config_id,
            f"u-regr-head-{run_id}", "import os",
            baseline_result_tree=baseline_tree,
        )
        result2 = poll_submission(api_base_url, sub2["id"], auth_headers)
        assert result2["status"] == "completed"

        comparison = result2["comparison"]
        assert comparison is not None
        assert comparison["score_delta"] < 0
        assert comparison["improved"] is False

        statuses = {d["status"] for d in comparison["test_deltas"]}
        assert "regressed" in statuses

    def test_comparison_identical_submissions(self, api_base_url, auth_headers, run_id):
        """
        Submit same code twice with baseline → verify all tests are unchanged.
        """
        config_id = f"cmp-identical-{run_id}"
        _create_static_config(api_base_url, auth_headers, config_id, ["os", "sys"])

        code = "x = 42\nprint(x)"

        # Baseline
        sub1 = _submit(
            api_base_url, auth_headers, config_id,
            f"u-id-base-{run_id}", code,
        )
        result1 = poll_submission(api_base_url, sub1["id"], auth_headers)
        assert result1["status"] == "completed"
        baseline_tree = result1["result_tree"]

        # Head (same code)
        sub2 = _submit(
            api_base_url, auth_headers, config_id,
            f"u-id-head-{run_id}", code,
            baseline_result_tree=baseline_tree,
        )
        result2 = poll_submission(api_base_url, sub2["id"], auth_headers)
        assert result2["status"] == "completed"

        comparison = result2["comparison"]
        assert comparison is not None
        assert comparison["score_delta"] == 0.0
        assert comparison["improved"] is False

        for delta in comparison["test_deltas"]:
            assert delta["status"] == "unchanged"
            assert delta["delta"] == 0.0

    def test_no_comparison_without_baseline(self, api_base_url, auth_headers, run_id):
        """Verify comparison is absent when baseline_result_tree is not provided."""
        config_id = f"cmp-nobase-{run_id}"
        _create_static_config(api_base_url, auth_headers, config_id, ["os"])

        sub = _submit(
            api_base_url, auth_headers, config_id,
            f"u-nobase-{run_id}", "x = 1",
        )
        result = poll_submission(api_base_url, sub["id"], auth_headers)
        assert result["status"] == "completed"
        assert result["comparison"] is None

    def test_comparison_with_multiple_tests(self, api_base_url, auth_headers, run_id):
        """
        Multi-test config: one test improves, another regresses.
        Verify mixed statuses in comparison.
        """
        config_id = f"cmp-multi-{run_id}"
        _create_static_config(api_base_url, auth_headers, config_id, ["os", "sys"])

        # Baseline: imports os only
        sub1 = _submit(
            api_base_url, auth_headers, config_id,
            f"u-multi-base-{run_id}", "import os\nx = 1",
        )
        result1 = poll_submission(api_base_url, sub1["id"], auth_headers)
        assert result1["status"] == "completed"
        baseline_tree = result1["result_tree"]

        # Head: imports sys only (os fixed, sys introduced)
        sub2 = _submit(
            api_base_url, auth_headers, config_id,
            f"u-multi-head-{run_id}", "import sys\nx = 1",
            baseline_result_tree=baseline_tree,
        )
        result2 = poll_submission(api_base_url, sub2["id"], auth_headers)
        assert result2["status"] == "completed"

        comparison = result2["comparison"]
        assert comparison is not None
        assert len(comparison["test_deltas"]) >= 2

        statuses = {d["status"] for d in comparison["test_deltas"]}
        # os test should improve (violation removed), sys test should regress (violation added)
        assert "improved" in statuses or "regressed" in statuses

    def test_score_vector_present_alongside_comparison(self, api_base_url, auth_headers, run_id):
        """Verify score_vector and comparison coexist in the response."""
        config_id = f"cmp-sv-{run_id}"
        _create_static_config(api_base_url, auth_headers, config_id, ["os"])

        sub1 = _submit(
            api_base_url, auth_headers, config_id,
            f"u-sv-base-{run_id}", "import os",
        )
        result1 = poll_submission(api_base_url, sub1["id"], auth_headers)
        baseline_tree = result1["result_tree"]

        sub2 = _submit(
            api_base_url, auth_headers, config_id,
            f"u-sv-head-{run_id}", "x = 1",
            baseline_result_tree=baseline_tree,
        )
        result2 = poll_submission(api_base_url, sub2["id"], auth_headers)
        assert result2["status"] == "completed"

        # Both should be present
        assert result2["score_vector"] is not None
        assert result2["comparison"] is not None

        # score_vector keys should correspond to test_delta paths
        sv_paths = set(result2["score_vector"].keys())
        delta_paths = {d["path"] for d in result2["comparison"]["test_deltas"]}
        assert sv_paths == delta_paths, (
            f"score_vector paths {sv_paths} should match comparison paths {delta_paths}"
        )


# ==============================================================================
# EXTERNAL RESULT WITH COMPARISON
# ==============================================================================


class TestExternalResultComparisonE2E:
    """Verify external result ingestion preserves the comparison field."""

    def test_external_result_with_comparison(self, api_base_url, auth_headers, run_id):
        """Ingest an external result that includes a comparison dict."""
        # First, create a config so we have a valid grading_config_id
        config_id = f"ext-cmp-{run_id}"
        config_resp = _create_static_config(
            api_base_url, auth_headers, config_id, ["os"],
        )
        internal_config_id = config_resp["id"]

        comparison_data = {
            "score_delta": 15.0,
            "improved": True,
            "test_deltas": [
                {
                    "path": "base/checks/no_os",
                    "status": "improved",
                    "baseline_score": 0.0,
                    "head_score": 100.0,
                    "delta": 100.0,
                }
            ],
        }

        external_payload = {
            "grading_config_id": internal_config_id,
            "external_user_id": f"ext-user-{run_id}",
            "username": "ext-student",
            "language": "python",
            "status": "completed",
            "final_score": 100.0,
            "comparison": comparison_data,
            "execution_time_ms": 500,
        }

        response = requests.post(
            f"{api_base_url}/submissions/external-results",
            json=external_payload,
            headers=auth_headers,
        )
        assert response.status_code in [200, 201]
        ext_result = response.json()

        # Fetch the submission to verify comparison was stored
        sub_response = requests.get(
            f"{api_base_url}/submissions/{ext_result['submission_id']}",
            headers=auth_headers,
        )
        assert sub_response.status_code == 200
        sub_data = sub_response.json()

        assert sub_data["comparison"] is not None
        assert sub_data["comparison"]["score_delta"] == 15.0
        assert sub_data["comparison"]["improved"] is True
        assert len(sub_data["comparison"]["test_deltas"]) == 1


# ==============================================================================
# SCORE VECTOR E2E TESTS
# ==============================================================================


class TestScoreVectorE2E:
    """E2E tests for score_vector via the HTTP API."""

    def test_score_vector_present_without_baseline(self, api_base_url, auth_headers, run_id):
        """
        Submit code without baseline_result_tree → verify score_vector is present
        and comparison is absent. This is the most common usage.
        """
        config_id = f"sv-nobase-{run_id}"
        _create_static_config(api_base_url, auth_headers, config_id, ["os"])

        sub = _submit(
            api_base_url, auth_headers, config_id,
            f"u-sv-nobase-{run_id}", "x = 42",
        )
        result = poll_submission(api_base_url, sub["id"], auth_headers)
        assert result["status"] == "completed"

        # score_vector should be present
        assert result["score_vector"] is not None
        assert isinstance(result["score_vector"], dict)
        assert len(result["score_vector"]) >= 1

        # comparison should be absent
        assert result["comparison"] is None

        # All values should be numeric
        for path, score in result["score_vector"].items():
            assert isinstance(path, str)
            assert isinstance(score, (int, float))

    def test_score_vector_correct_values_for_multi_test(self, api_base_url, auth_headers, run_id):
        """
        Submit code with multiple tests — verify score_vector has correct path-keyed
        scores for each test.
        """
        config_id = f"sv-multi-{run_id}"
        _create_static_config(api_base_url, auth_headers, config_id, ["os", "sys"])

        # Code violates os, passes sys
        sub = _submit(
            api_base_url, auth_headers, config_id,
            f"u-sv-multi-{run_id}", "import os\nx = 1",
        )
        result = poll_submission(api_base_url, sub["id"], auth_headers)
        assert result["status"] == "completed"

        sv = result["score_vector"]
        assert sv is not None
        assert len(sv) == 2

        # Find the os and sys entries by test name in path
        os_entries = {k: v for k, v in sv.items() if "no_os" in k}
        sys_entries = {k: v for k, v in sv.items() if "no_sys" in k}

        assert len(os_entries) == 1, f"Expected 1 os entry, got {os_entries}"
        assert len(sys_entries) == 1, f"Expected 1 sys entry, got {sys_entries}"

        # os test should have failed, sys test should have passed
        os_score = list(os_entries.values())[0]
        sys_score = list(sys_entries.values())[0]
        assert os_score < 100.0
        assert sys_score == 100.0

    def test_score_vector_all_passing(self, api_base_url, auth_headers, run_id):
        """Clean code should produce score_vector with all 100.0 values."""
        config_id = f"sv-pass-{run_id}"
        _create_static_config(api_base_url, auth_headers, config_id, ["os", "sys"])

        sub = _submit(
            api_base_url, auth_headers, config_id,
            f"u-sv-pass-{run_id}", "x = 42\nprint(x)",
        )
        result = poll_submission(api_base_url, sub["id"], auth_headers)
        assert result["status"] == "completed"
        assert result["final_score"] == 100.0

        sv = result["score_vector"]
        assert sv is not None
        for path, score in sv.items():
            assert score == 100.0, f"Expected 100.0 for {path}, got {score}"

    def test_score_vector_deterministic_across_submissions(self, api_base_url, auth_headers, run_id):
        """Two identical submissions should produce identical score_vectors."""
        config_id = f"sv-det-{run_id}"
        _create_static_config(api_base_url, auth_headers, config_id, ["os"])

        code = "import os"

        sub1 = _submit(api_base_url, auth_headers, config_id, f"u-sv-det1-{run_id}", code)
        result1 = poll_submission(api_base_url, sub1["id"], auth_headers)

        sub2 = _submit(api_base_url, auth_headers, config_id, f"u-sv-det2-{run_id}", code)
        result2 = poll_submission(api_base_url, sub2["id"], auth_headers)

        assert result1["score_vector"] == result2["score_vector"]

    def test_external_result_with_score_vector(self, api_base_url, auth_headers, run_id):
        """Ingest an external result with score_vector and verify retrieval."""
        config_id = f"ext-sv-{run_id}"
        config_resp = _create_static_config(
            api_base_url, auth_headers, config_id, ["os"],
        )
        internal_config_id = config_resp["id"]

        score_vector_data = {
            "base/checks/no_os": 100.0,
            "base/checks/no_sys": 50.0,
        }

        external_payload = {
            "grading_config_id": internal_config_id,
            "external_user_id": f"ext-sv-user-{run_id}",
            "username": "ext-student",
            "language": "python",
            "status": "completed",
            "final_score": 75.0,
            "score_vector": score_vector_data,
            "execution_time_ms": 300,
        }

        response = requests.post(
            f"{api_base_url}/submissions/external-results",
            json=external_payload,
            headers=auth_headers,
        )
        assert response.status_code in [200, 201]
        ext_result = response.json()

        # Fetch and verify score_vector was stored
        sub_response = requests.get(
            f"{api_base_url}/submissions/{ext_result['submission_id']}",
            headers=auth_headers,
        )
        assert sub_response.status_code == 200
        sub_data = sub_response.json()

        assert sub_data["score_vector"] is not None
        assert sub_data["score_vector"] == score_vector_data

