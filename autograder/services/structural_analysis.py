"""Parser rules for source-code analysis; no grader-level or cross-run state.

This module is the only owner of grammar selection. A grammar is chosen from
each selected file's own type, so a mixed web submission keeps HTML, CSS and
JavaScript apart even though its runtime language is ``node``. The runtime
language is consulted only to decide which source files belong to it and to
disambiguate C/C++ headers.
"""
from pathlib import PurePosixPath
from typing import Optional

from autograder.models.evaluation_error import EvaluationError
from autograder.models.language import Language

try:
    from ast_grep_py import SgRoot
except ImportError:
    SgRoot = None

#: Positive source declarations; documents and configuration never reach a code grammar.
SOURCE_GRAMMARS = {
    ".py": "python", ".java": "java", ".js": "javascript",
    ".mjs": "javascript", ".cjs": "javascript", ".c": "c",
    ".cpp": "cpp", ".cc": "cpp", ".cxx": "cpp", ".hpp": "cpp",
    ".h": "c",
}
#: The grammar of each runtime language's own source files.
RUNTIME_GRAMMARS = {
    Language.PYTHON: "python", Language.JAVA: "java", Language.NODE: "javascript",
    Language.CPP: "cpp", Language.C: "c",
}


def source_grammar(filename: str, language: Optional[Language] = None) -> Optional[str]:
    """The grammar declared by a file's type; C headers follow a C++ runtime."""
    suffix = PurePosixPath(filename).suffix.lower()
    if suffix == ".h" and language == Language.CPP:
        return "cpp"
    return SOURCE_GRAMMARS.get(suffix)


def is_runtime_source(filename: str, language: Optional[Language]) -> bool:
    """Whether a file is source code of the runtime language (any source without one)."""
    grammar = source_grammar(filename, language)
    expected = RUNTIME_GRAMMARS.get(language) if language is not None else None
    return grammar is not None and (expected is None or grammar == expected)


def parse_source(file, language: Optional[Language] = None):
    """Parse a declared source grammar, preserving capability errors."""
    grammar = source_grammar(file.filename, language)
    if SgRoot is None or grammar is None:
        raise EvaluationError("CAPABILITY_UNAVAILABLE", "Structural analysis is unavailable for this assessment.", "capability")
    try:
        return SgRoot(file.content, grammar)
    except Exception as exc:
        raise EvaluationError("CAPABILITY_UNAVAILABLE", "Structural analysis is unavailable for this assessment.", "capability") from exc
