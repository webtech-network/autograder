"""Trusted Python extension example; run with ``python -m examples.contracts.custom_evaluator``."""

from pydantic import BaseModel, Field

from autograder import (
    compile_definition, evaluate_submission, Template, TestFunction,
    Submission, SubmissionFile, TestResult,
)
from autograder.models.dataclass.param_description import ParamDescription


class ContainsTextParameters(BaseModel):
    needle: str = Field(min_length=1)


class ContainsText(TestFunction):
    name = "contains_text"
    description = "Check whether any selected file contains a literal string."
    parameter_description = [ParamDescription("needle", "Text to find", "string")]
    config_schema = ContainsTextParameters

    def execute(self, files, sandbox, *, needle: str, **kwargs) -> TestResult:
        found = any(needle in file.content for file in (files or []))
        return TestResult(self.name, 100 if found else 0, "Found" if found else "Missing")


class TrustedTextTemplate(Template):
    tests = {"contains_text": ContainsText()}
    template_name = "Trusted text"
    template_description = "One local, trusted evaluator"
    requires_sandbox = False

    def get_test(self, name):
        return self.tests[name]


DEFINITION = {
    "schema_version": "1.0",
    "templates": ["trusted_text"],
    "languages": ["node"],
    "criteria": {
        "base": {
            "weight": 100,
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
        templates={"trusted_text": TrustedTextTemplate()},
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
