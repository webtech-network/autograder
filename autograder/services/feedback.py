"""Requested feedback: an optional derivation of a completed grade.

The pipeline calls ``render_feedback`` only when the definition enables
feedback. It ranks the completed tree's criteria by impact and renders the
one implemented report mode with the definition's canonical preferences.
"""
from autograder.models.contracts.definition import FeedbackPreferences
from autograder.models.contracts.outcome import ResultOutcomeTree
from autograder.services.focus_service import find_focus
from autograder.services.report.default_reporter import render_default_report


def render_feedback(tree: ResultOutcomeTree, preferences: FeedbackPreferences, locale: str) -> str:
    """Return Markdown feedback; raise if the report cannot be produced."""
    content = render_default_report(find_focus(tree), tree, preferences, locale)
    if not isinstance(content, str) or not content.strip():
        raise ValueError("Feedback rendering produced no content")
    return content
