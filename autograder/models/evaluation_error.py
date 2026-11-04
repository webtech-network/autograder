"""A required evaluation failed to produce an authoritative assessment."""
from autograder.models.contracts.outcome import ENGINE_ERROR_CODES


class EvaluationError(Exception):
    """Carries one published engine code (see OUTCOMES.md) and a fixed safe message."""

    def __init__(self, code: str, message: str, category: str = "internal", retryable: bool = False):
        if code not in ENGINE_ERROR_CODES:
            # An unpublished code is a programming error: the pipeline reports it as EXECUTION_ERROR.
            raise ValueError(f"Unpublished evaluation error code: {code!r}")
        super().__init__(message)
        self.code = code
        self.message = message
        self.category = category
        self.retryable = retryable
