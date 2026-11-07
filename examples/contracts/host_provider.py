"""An offline AI host example: python -m examples.contracts.host_provider.

The demonstration provider returns canned assessments. Replace it with a trusted
provider for real assessment; the engine never constructs a client implicitly.
"""
from autograder import (
    AiTestFunction, EvaluationInput, HostCapabilities, ProviderAssessment, Submission, SubmissionFile,
    Template, evaluate_submission,
)


class Review(AiTestFunction):
    """AI evaluators declare build_prompt(evaluation, *, <parameters>); the host provider assesses."""
    name = "review"
    description = "Review code clarity."

    def build_prompt(self, evaluation: EvaluationInput) -> str:
        names = ", ".join(file.filename for file in evaluation.files)
        return f"Assess the clarity of the selected source code: {names}."


TEMPLATE = Template("Review", "Trusted review example.", [Review()])


class DemonstrationProvider:
    """One call per batch; one assessment per requested criterion ID."""
    def assess(self, requests, *, context_files, locale):
        return [ProviderAssessment(request.criterion_id, 100, "Demonstration assessment.") for request in requests]


DEFINITION = {"schema_version": "2.0", "languages": ["python"],
              "criteria": {"base": {"tests": [
                  {"id": "clarity", "type": "review", "name": "Code clarity", "parameters": {}}]}}}


def run_example():
    return evaluate_submission(
        Submission("example", "example", "example", {"main.py": SubmissionFile("main.py", "print('hello')")}),
        definition=DEFINITION, templates={"review": TEMPLATE},
        capabilities=HostCapabilities(ai=DemonstrationProvider()),
    )


if __name__ == "__main__":
    print(run_example().model_dump_json(indent=2))
