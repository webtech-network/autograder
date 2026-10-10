"""Lazy AST parsing owned by static assessment, cached for one grading traversal."""
from autograder.models.evaluation_error import EvaluationError
from autograder.services.file_selection import source_grammar

try:
    from ast_grep_py import SgRoot
except ImportError:
    SgRoot = None


class StructuralAnalysisCache:
    """Reuse parsed source only for the grader that owns this cache."""
    def __init__(self):
        self._roots = {}

    def root_for(self, file, language=None):
        """Parse a declared source grammar on demand, preserving capability errors."""
        grammar = source_grammar(file.filename, language)
        if SgRoot is None or grammar is None:
            raise EvaluationError("CAPABILITY_UNAVAILABLE", "Structural analysis is unavailable for this assessment.", "capability")
        key = (grammar, file.content)
        if key not in self._roots:
            try:
                self._roots[key] = SgRoot(file.content, grammar)
            except Exception as exc:
                raise EvaluationError("CAPABILITY_UNAVAILABLE", "Structural analysis is unavailable for this assessment.", "capability") from exc
        return self._roots[key]
