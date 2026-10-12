"""Requested feedback renders from the completed tree and explicit preferences."""
from autograder import build_pipeline
from tests.unit.pipeline.test_terminal_outcome import definition, submission


def test_feedback_includes_configured_title_and_grade():
    value = definition(feedback=True)
    value["feedback"]["preferences"] = {"general": {"report_title": "Integration Test Title"}}
    outcome = build_pipeline(definition=value).run(submission("print(1)")).outcome
    assert outcome.status == "completed"
    assert outcome.feedback.status == "completed"
    assert "Integration Test Title" in outcome.feedback.content
    assert "GRADING SUMMARY" in outcome.feedback.content
