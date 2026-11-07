"""Requested feedback example; run with ``python -m examples.contracts.requested_feedback``.

Feedback is an optional derivation of a completed grade. With
``feedback.enabled`` false the engine does no focus or report work and the
outcome says ``disabled``; when enabled, the default Markdown report is rendered
from the completed tree with the definition's preferences. A feedback failure
would keep the grade and report ``failed`` separately.
"""
from copy import deepcopy

from autograder import Submission, SubmissionFile, evaluate_submission

DEFINITION = {
    "schema_version": "2.0",
    "languages": ["python"],
    "criteria": {"base": {"tests": [
        {"id": "no-os", "type": "forbidden_import", "name": "Avoid os", "weight": 3,
         "parameters": {"forbidden_imports": ["os"]}},
        {"id": "no-loops", "type": "forbidden_keyword", "name": "Avoid loops", "weight": 1,
         "parameters": {"forbidden_keywords": ["for_loop"]}},
    ]}},
    "feedback": {"enabled": False},
}


def grade(enabled: bool, locale: str = "en"):
    definition = deepcopy(DEFINITION)
    if enabled:
        definition["feedback"] = {"enabled": True, "preferences": {"general": {
            "report_title": "Import review",
            "online_content": [{"url": "https://docs.python.org/3/library/os.html",
                                "description": "The os module", "linked_tests": ["no-os"]}]}}}
    submission = Submission("student", "student", "feedback-example",
                            {"main.py": SubmissionFile("main.py", "import os\nprint(os.getcwd())\n")}, locale=locale)
    return evaluate_submission(submission, definition=definition)


if __name__ == "__main__":
    disabled, enabled = grade(False), grade(True)
    print("disabled:", disabled.status, disabled.score, disabled.feedback.status)
    print("enabled:", enabled.status, enabled.score, enabled.feedback.status)
    print(enabled.feedback.content)
    if (disabled.feedback.status, enabled.feedback.status) != ("disabled", "completed"):
        raise SystemExit(1)
