"""ast-grep parsing for structural evaluators; no grader-level or cross-run state."""
from autograder.models.evaluation_error import EvaluationError
from autograder.services.file_selection import source_grammar

try:
    from ast_grep_py import SgRoot
except ImportError:
    SgRoot = None


def parse_source(file, language=None):
    """Parse a declared source grammar, preserving capability errors."""
    grammar = source_grammar(file.filename, language)
    if SgRoot is None or grammar is None:
        raise EvaluationError("CAPABILITY_UNAVAILABLE", "Structural analysis is unavailable for this assessment.", "capability")
    try:
        return SgRoot(file.content, grammar)
    except Exception as exc:
        raise EvaluationError("CAPABILITY_UNAVAILABLE", "Structural analysis is unavailable for this assessment.", "capability") from exc
