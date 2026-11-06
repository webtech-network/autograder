"""A required evaluation failed to produce an authoritative assessment."""
from typing import Any, Mapping

from autograder.models.contracts.outcome import ENGINE_ERROR_CODES


class EvaluationError(Exception):
    """Carries one published engine code (see OUTCOMES.md) and a fixed safe message.

    A ``submission`` failure may also explain itself to the student: an
    ``explanation`` is a translation key and its parameters, rendered in the
    submission's locale when the outcome is built, and ``output`` is the failing
    step's output, excerpted there to the report bound. Every other category
    keeps its fixed message, so infrastructure details never reach the outcome.
    """

    def __init__(self, code: str, message: str, category: str = "internal", retryable: bool = False, *,  # pylint: disable=too-many-arguments
                 explanation: tuple[str, Mapping[str, Any]] | None = None, output: str | None = None):
        if code not in ENGINE_ERROR_CODES:
            # An unpublished code is a programming error: the pipeline reports it as EXECUTION_ERROR.
            raise ValueError(f"Unpublished evaluation error code: {code!r}")
        if (explanation is not None or output is not None) and category != "submission":
            raise ValueError("Only submission failures carry an explanation or output")
        super().__init__(message)
        self.code = code
        self.message = message
        self.category = category
        self.retryable = retryable
        self.explanation = explanation
        self.output = output
