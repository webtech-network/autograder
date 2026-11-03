"""The trusted evaluator extension contract.

An evaluator is a local change: implement ``execute``, declare its parameter
contract and register the instance in a ``Template``::

    class ContainsText(TestFunction):
        name = "contains_text"
        description = "Check whether a selected file contains a literal string."

        def execute(self, evaluation: EvaluationInput, *,
                    needle: Annotated[str, Field(min_length=1, description="Text to find")]) -> TestResult:
            found = any(needle in file.content for file in evaluation.files)
            return TestResult(self.name, 100 if found else 0, "Found" if found else "Missing")

Keyword-only parameters are the normalized configuration (see
``autograder.models.contracts.parameter_contract``); ``evaluation`` is the
small typed runtime input. Evaluator instances are shared by every submission
and thread that uses their template, so they must be stateless: keep
per-submission state in local variables of the call, never on ``self``.
"""
from abc import ABC, abstractmethod
from pathlib import PurePosixPath
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, NamedTuple, Optional, Tuple, Type

from pydantic import BaseModel

from autograder.models.dataclass.submission import SubmissionFile
from autograder.models.dataclass.test_result import TestResult
from autograder.models.execution import ExecutionSession
from autograder.models.language import Language


@dataclass(frozen=True)
class EvaluationInput:
    """Runtime input for one assessment; never configuration.

    ``files`` are the selected assessment files (see FILES.md); each file keeps
    its opaque ``metadata`` and ``changed_lines``. ``session`` is supplied only to
    evaluators that declare an execution capability (``sandbox_execution`` or
    ``http_network``); every other evaluator receives ``None``.
    """
    files: Tuple[SubmissionFile, ...] = ()
    language: Optional[Language] = None
    locale: str = "en"
    session: Optional[ExecutionSession] = None


class ParameterIssue(NamedTuple):
    """One definition error found by an evaluator-owned semantic check.

    ``path`` is relative to the criterion's ``parameters`` object.
    """
    code: str
    path: Tuple[Any, ...]
    message: str


class TestFunction(ABC):
    """A trusted, stateless evaluator invoked as ``execute(evaluation, **parameters)``."""

    #: Assessment input contract. Defaults allow zero or more files of any type.
    file_extensions: Optional[Tuple[str, ...]] = None
    minimum_files: int = 0
    maximum_files: Optional[int] = None
    #: Whole-submission checks and execution need their inputs even outside scope.
    uses_context_files: bool = False
    #: Multi-file checks can name their required inputs in normalized parameters.
    file_parameters: Tuple[str, ...] = ()

    #: Host capabilities this evaluator needs (see catalog.Capability). Evaluators
    #: declaring sandbox_execution or http_network receive the execution session.
    required_capabilities: Tuple[str, ...] = ()
    #: Known evaluator language constraints; None declares no specific restriction.
    supported_languages: Optional[List[str]] = None
    #: Optional catalog example; otherwise required fields are synthesized from config_schema.
    example_parameters: Optional[Dict[str, Any]] = None

    @property
    def config_schema(self) -> Type[BaseModel]:
        """The parameter contract: derived from the entry point's keyword-only
        parameters unless an evaluator supplies an explicit Pydantic model."""
        from autograder.models.contracts.parameter_contract import signature_contract
        return signature_contract(self)

    @property
    def entrypoint(self):
        """The method whose keyword-only parameters are the configuration."""
        return self.execute

    @property
    @abstractmethod
    def name(self) -> str:
        """The registry identifier (e.g., 'has_tag')."""

    @property
    @abstractmethod
    def description(self) -> str:
        """A description of what the evaluator assesses."""

    def accepts_file(self, filename: str, language: Optional[Language]) -> bool:
        """Whether this evaluator can assess ``filename`` (see FILES.md).

        The default honours ``file_extensions``. Evaluators that parse source
        code override it with their own parser rules, so file types are decided
        by the analysis implementation, never by a generic language table.
        """
        del language
        return self.file_extensions is None or PurePosixPath(filename).suffix.lower() in self.file_extensions

    def validate_parameters(self, parameters: Dict[str, Any], *,
                            languages: Tuple[str, ...]) -> Iterable[ParameterIssue]:
        """Optional pure definition check of normalized ``parameters``.

        Called by ``compile_definition``/``compile_snapshot`` with an isolated copy
        and the definition's allowed languages, for semantics a JSON contract
        cannot express. It must not perform I/O or depend on submission state.
        """
        del parameters, languages
        return ()

    @abstractmethod
    def execute(self, evaluation: EvaluationInput, /, **parameters) -> TestResult:
        """Assess ``evaluation`` with the normalized configuration."""
