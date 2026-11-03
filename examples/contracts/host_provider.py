"""An offline AI host example: python -m examples.contracts.host_provider.

The demonstration provider returns canned assessments. Replace it with a trusted
provider for real assessment; the engine never constructs a client implicitly.
"""
from autograder import (
    AiTestFunction, EvaluationInput, HostCapabilities, Submission, SubmissionFile, Template,
    TestResult, evaluate_submission,
)


class Review(AiTestFunction):
    """AI evaluators declare build_prompt(evaluation, *, <parameters>); the host provider assesses."""
    name = "review"
    description = "Review code clarity."

    def build_prompt(self, evaluation: EvaluationInput) -> str:
        names = ", ".join(file.filename for file in evaluation.files)
        return f"Assess the clarity of the selected source code: {names}."


class ReviewTemplate(Template):
    template_name = "review"
    template_description = "Trusted review example."
    requires_sandbox = False

    def __init__(self):
        self.tests = {"review": Review()}


class DemonstrationProvider:
    def run(self, tests, submission_files, locale="en"):
        return {test.test_name: TestResult(test.test_name, 100, "Demonstration assessment.") for test in tests}


DEFINITION = {"schema_version": "1.0", "templates": ["review"], "languages": ["python"],
              "criteria": {"base": {"weight": 100, "tests": [
                  {"id": "clarity", "type": "review", "name": "Code clarity", "parameters": {}}]}}}


def run_example():
    return evaluate_submission(
        Submission("example", "example", "example", {"main.py": SubmissionFile("main.py", "print('hello')")}),
        definition=DEFINITION, templates={"review": ReviewTemplate()},
        capabilities=HostCapabilities(ai=DemonstrationProvider()),
    )


if __name__ == "__main__":
    print(run_example().model_dump_json(indent=2))
