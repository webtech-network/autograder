"""A trusted template: a named collection of evaluator instances."""
from typing import Dict, Iterable

from autograder.models.abstract.test_function import TestFunction
from autograder.models.process import MAX_TIMEOUT_SECONDS


def check_process_timeouts(evaluator: TestFunction) -> None:
    """An evaluator that runs processes declares each one's deadline (the execution budget's source)."""
    timeouts = evaluator.process_timeouts
    if not isinstance(timeouts, tuple) or any(
            isinstance(value, bool) or not isinstance(value, (int, float))
            or not 0 < value <= MAX_TIMEOUT_SECONDS for value in timeouts):
        raise TypeError(f"Evaluator '{evaluator.name}': process_timeouts must be a tuple of deadlines "
                        f"in (0, {MAX_TIMEOUT_SECONDS}] seconds.")
    if "sandbox_execution" in evaluator.required_capabilities and not timeouts:
        raise TypeError(f"Evaluator '{evaluator.name}' declares sandbox_execution, so it must declare "
                        "process_timeouts: the deadline of every process one assessment may run.")


class Template:
    """``Template(name, description, evaluators)``.

    Each evaluator is registered under its own ``name``; the template never
    restates identifiers. Requirements such as execution are declared by each
    evaluator (``required_capabilities``), never by the template.
    """

    def __init__(self, name: str, description: str, evaluators: Iterable[TestFunction]):
        self.template_name = name
        self.template_description = description
        self.evaluators = tuple(evaluators)

    def get_tests(self) -> Dict[str, TestFunction]:
        """Return the registry ``{evaluator.name: evaluator}``."""
        return {evaluator.name: evaluator for evaluator in self.evaluators}

    def get_test(self, name: str) -> TestFunction:
        """Return a registered evaluator by its identifier."""
        try:
            return self.get_tests()[name]
        except KeyError:
            raise KeyError(f"Evaluator '{name}' is not registered in template '{self.template_name}'") from None

    def validate_contract(self) -> None:
        """Validate evaluator types, unique identifiers and each evaluator's call shape."""
        from autograder.models.contracts.parameter_contract import check_invocation
        if not isinstance(getattr(self, "evaluators", None), tuple):
            # e.g. a subclass written the pre-ONB-08 way: sets ``self.tests`` and skips super().__init__.
            raise TypeError("Templates must be built with Template(name, description, evaluators); "
                            "a subclass must call super().__init__ instead of setting a tests dict.")
        seen = set()
        for evaluator in self.evaluators:
            if not isinstance(evaluator, TestFunction):
                raise TypeError("Template evaluators must be TestFunction instances.")
            if not isinstance(evaluator.name, str) or not evaluator.name:
                raise TypeError("Evaluator identifiers must be nonempty strings.")
            if evaluator.name in seen:
                raise ValueError(f"Duplicate evaluator identifier in template: {evaluator.name}")
            seen.add(evaluator.name)
            check_invocation(evaluator)
            check_process_timeouts(evaluator)
        # Compilation and discovery read get_tests(); it must be exactly the evaluators by name.
        registry = self.get_tests()
        if registry.keys() != seen or any(registry[e.name] is not e for e in self.evaluators):
            raise TypeError("A template's get_tests() must return {evaluator.name: evaluator} for its "
                            "evaluators; do not override it.")
