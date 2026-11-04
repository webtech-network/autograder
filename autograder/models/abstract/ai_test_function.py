"""Evaluators whose assessment is delegated to the host AI provider."""
from abc import abstractmethod

from autograder.models.abstract.test_function import EvaluationInput, TestFunction
from autograder.models.dataclass.test_result import TestResult
from autograder.models.evaluation_error import EvaluationError


class AiTestFunction(TestFunction):
    """An AI evaluator declares ``build_prompt(self, evaluation, *, <parameters>)``.

    Adding one means writing the prompt builder, its parameter contract,
    registration and tests. ``assess_many`` (``autograder.services.assessment``)
    builds every selected AI criterion's prompt and sends the group to the
    host-supplied provider in one call, keyed by criterion ID. AI evaluators are
    never executed individually and receive no provider client.
    """

    required_capabilities = ("ai_provider",)

    @property
    def entrypoint(self):
        return self.build_prompt

    @abstractmethod
    def build_prompt(self, evaluation: EvaluationInput, /, **parameters) -> str:
        """Return the prompt describing what the provider must assess."""

    def execute(self, evaluation: EvaluationInput, /, **parameters) -> TestResult:
        """AI criteria are assessed only through the provider batch."""
        raise EvaluationError("PROVIDER_UNAVAILABLE", "An AI assessment requires a host-supplied provider.", "provider")
