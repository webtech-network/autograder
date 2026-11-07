"""Requested feedback over real HTTP calls and the durable worker (ARC-12)."""
from unittest.mock import patch

import pytest

from autograder.models.contracts.definition import FeedbackPreferences
from autograder.models.contracts.outcome import ResultOutcomeTree
from autograder.services.feedback import render_feedback

HEADERS = {"Authorization": "Bearer feedback-token"}


@pytest.fixture(autouse=True)
def integration_token(monkeypatch):
    monkeypatch.setenv("AUTOGRADER_INTEGRATION_TOKEN", "feedback-token")


def definition(feedback):
    return {"schema_version": "2.0", "languages": ["python"],
            "criteria": {"base": {"tests": [
                {"id": "imports", "type": "forbidden_import", "name": "Imports / os", "weight": 3,
                 "parameters": {"forbidden_imports": ["os"]}},
                {"id": "loops", "type": "forbidden_keyword", "name": "Imports / os", "weight": 1,
                 "parameters": {"forbidden_keywords": ["for_loop"]}}]}},
            "feedback": feedback}


ENABLED = {"enabled": True, "preferences": {
    "general": {"report_title": "Your report", "online_content": [
        {"url": "https://example.com/imports", "description": "Imports", "linked_tests": ["imports"]},
        {"url": "https://example.com/loops", "description": "Loops", "linked_tests": ["loops"]}]},
    "default": {"category_headers": {"base": "Requirements"}}}}


async def grade(client, application, assignment, feedback, locale=None):
    created = await client.post("/api/v1/configs", json={"external_assignment_id": assignment,
                                                          "definition": definition(feedback)})
    assert created.status_code == 200, created.text
    payload = {"external_assignment_id": assignment, "external_user_id": "student", "username": "Student",
               "files": [{"filename": "main.py", "content": "import os\nprint(1)\n"}]}
    if locale:
        payload["locale"] = locale
    submitted = await client.post("/api/v1/submissions", json=payload)
    assert submitted.status_code == 202, submitted.text
    while await application.state.host.worker.run_once():
        pass
    polled = (await client.get(submitted.headers["Location"])).json()
    details = await client.get(f'/api/v1/submissions/{polled["id"]}/details', headers=HEADERS)
    assert details.status_code == 200, details.text
    return polled, details.json()["outcome"]


@pytest.mark.asyncio
async def test_disabled_feedback_does_no_work_even_when_feedback_services_fail(test_client, application):
    broken = RuntimeError("feedback services unavailable")
    with patch("autograder.services.feedback.find_focus", side_effect=broken) as focus, \
         patch("autograder.services.feedback.render_default_report", side_effect=broken) as report:
        polled, outcome = await grade(test_client, application, "feedback-off", {"enabled": False})
    focus.assert_not_called()
    report.assert_not_called()
    assert polled["status"] == "completed" and polled["final_score"] == 25
    assert polled["feedback_status"] == "disabled"
    assert outcome["feedback"] == {"status": "disabled", "content": None, "error": None}


@pytest.mark.asyncio
@pytest.mark.parametrize("locale,final,lost", [(None, "**Final score: 25.00 / 100**", "−75.00 points"),
                                               ("pt_br", "**Nota final: 25.00 / 100**", "−75.00 pontos")])
async def test_enabled_feedback_is_rendered_from_the_completed_grade(test_client, application, locale, final, lost):
    polled, outcome = await grade(test_client, application, f"feedback-on-{locale}", ENABLED, locale)
    assert polled["status"] == "completed" and polled["final_score"] == 25
    assert polled["feedback_status"] == "completed"
    content = outcome["feedback"]["content"]
    # The stored details round-trip: the text is the pure rendering of the returned tree.
    preferences = FeedbackPreferences.model_validate(ENABLED["preferences"])
    assert content == render_feedback(ResultOutcomeTree.model_validate(outcome["tree"]), preferences, locale or "en")
    assert content.startswith(f"# Your report\n\n{final}\n")
    assert f"## Requirements · 25.00 / 100 · {lost}" in content and "100 − 75.00 = **25.00 / 100**" in content
    assert content.count("**Imports / os**") == 1  # the passing criterion is hidden
    assert "forbidden" not in content and "for_loop" not in content  # parameters are never rendered
    assert "https://example.com/imports" in content and "https://example.com/loops" not in content


@pytest.mark.asyncio
async def test_enabled_feedback_failure_keeps_the_grade_with_a_separate_status(test_client, application):
    with patch("autograder.services.feedback.render_default_report", side_effect=RuntimeError("secret detail")):
        polled, outcome = await grade(test_client, application, "feedback-broken", ENABLED)
    assert polled["status"] == "completed" and polled["final_score"] == 25 and polled["error"] is None
    assert polled["feedback_status"] == "failed"
    assert outcome["score"] == 25 and outcome["tree"]["base"]["tests"][0]["score"] == 0
    assert outcome["feedback"]["content"] is None
    assert outcome["feedback"]["error"]["code"] == "FEEDBACK_ERROR"
    assert outcome["feedback"]["error"]["message"] == "Feedback could not be generated."
    assert "secret detail" not in str(outcome)
