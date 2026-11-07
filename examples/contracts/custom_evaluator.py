"""Trusted Python extension example; run with ``python -m examples.contracts.custom_evaluator``.

A new evaluator is a local change: its implementation, its parameter contract
(the annotated keyword-only parameters of ``execute``) and its registration.
"""
from typing import Annotated

from pydantic import Field

from autograder import (
    compile_definition, evaluate_submission, EvaluationInput, Template, TestFunction,
    Submission, SubmissionFile, TestResult,
)


class ContainsText(TestFunction):
    """Stateless: everything about one submission arrives in the call."""
    name = "contains_text"
    description = "Check whether any selected file contains a literal string."

    def execute(self, evaluation: EvaluationInput, *,
                needle: Annotated[str, Field(min_length=1, description="Text to find")]) -> TestResult:
        found = any(needle in file.content for file in evaluation.files)
        return TestResult(self.name, 100 if found else 0, "Found" if found else "Missing")


#: Registration: a template is a named collection of evaluator instances, each
#: registered under its own ``name``.
TEMPLATE = Template("Trusted text", "One local, trusted evaluator", [ContainsText()])


DEFINITION = {
    "schema_version": "2.0",
    "languages": ["node"],
    "criteria": {
        "base": {
            "tests": [{
                "id": "greeting",
                "type": "contains_text",
                "name": "Greeting exists",
                "weight": 100,
                "parameters": {"needle": "Hello"},
            }],
        }
    },
}


def grade(content: str):
    compiled = compile_definition(
        DEFINITION,
        templates={"trusted_text": TEMPLATE},
    )
    submission = Submission(
        username="local",
        user_id="local",
        assignment_id="trusted-example",
        submission_files={"index.html": SubmissionFile("index.html", content)},
    )
    # The compiled definition retains the trusted instance; language is inferred.
    return evaluate_submission(submission, definition=compiled)


if __name__ == "__main__":
    outcome = grade("<h1>Hello</h1>")
    print(outcome.model_dump_json(indent=2))
    if outcome.status != "completed":
        raise SystemExit(1)
