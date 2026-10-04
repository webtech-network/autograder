"""A required evaluation failed to produce an authoritative assessment."""


class EvaluationError(Exception):
    def __init__(self, code: str, message: str, category: str = "internal", retryable: bool = False):
        super().__init__(message)
        self.code = code
        self.message = message
        self.category = category
        self.retryable = retryable
