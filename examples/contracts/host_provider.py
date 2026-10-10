"""An offline AI host example: python -m examples.contracts.host_provider.

The demonstration provider returns canned assessments. Replace it with a trusted
provider for real assessment; the engine never constructs a client implicitly.
"""
from pydantic import BaseModel, ConfigDict

from autograder import HostCapabilities, Submission, SubmissionFile, Template, TestResult, evaluate_submission
from autograder.models.abstract.ai_test_function import AiTestFunction


class Parameters(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Review(AiTestFunction):
    name = "review"
    description = "Review code clarity."
    parameter_description = []
    config_schema = Parameters

    def build_prompt(self, files, **kwargs):
        return "Assess the clarity of the selected source code."


class ReviewTemplate(Template):
    template_name = "review"
    template_description = "Trusted review example."
    requires_sandbox = False

    def __init__(self):
        self.tests = {"review": Review()}

    def get_test(self, name):
        return self.tests[name]


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
