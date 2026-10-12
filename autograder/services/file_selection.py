"""One assessment-file policy for ordinary and AI criteria.

Files outside the assessment remain available as context and sandbox input.
"""
from pathlib import PurePosixPath
from typing import Dict, List, Optional

from autograder.models.criteria_tree import TestNode
from autograder.models.dataclass.submission import EvaluationScope, SubmissionFile
from autograder.models.evaluation_error import EvaluationError

# Positive source declarations; never feed documents/configuration to a code grammar.
SOURCE_GRAMMARS = {
    ".py": "python", ".java": "java", ".js": "javascript",
    ".mjs": "javascript", ".cjs": "javascript", ".c": "c",
    ".cpp": "cpp", ".cc": "cpp", ".cxx": "cpp", ".hpp": "cpp",
    ".h": "c",
}
LANGUAGE_GRAMMARS = {"python": "python", "java": "java", "node": "javascript", "c": "c", "cpp": "cpp"}


def source_grammar(filename: str, language=None) -> Optional[str]:
    """Return a declared grammar, with runtime language disambiguating C headers."""
    grammar = SOURCE_GRAMMARS.get(PurePosixPath(filename).suffix.lower())
    # C headers have no unique grammar; the selected runtime disambiguates them.
    if PurePosixPath(filename).suffix.lower() == ".h" and getattr(language, "value", language) == "cpp":
        return "cpp"
    return grammar


def select_files(
    test: TestNode,
    submission_files: Dict[str, SubmissionFile],
    scope: Optional[EvaluationScope] = None,
    language=None,
) -> List[SubmissionFile]:
    """Resolve and validate every selected criterion without dropping it from the tree."""
    evaluator = test.test_function
    targets = test.file_target
    parameter_targets = [test.parameters[name] for name in evaluator.file_parameters if test.parameters.get(name)]
    if parameter_targets:
        if targets is not None and not set(parameter_targets).issubset(targets):
            raise EvaluationError("FILE_TARGET_CONFLICT", "Criterion file parameters conflict with its targets.", "submission")
        targets = parameter_targets
    scoped = set(scope.scoped_files) if scope is not None else None
    if targets is not None:
        if any(name not in submission_files for name in targets):
            raise EvaluationError("REQUIRED_FILE_MISSING", "A required assessment file is missing.", "submission")
        if scoped is not None and not set(targets).issubset(scoped):
            raise EvaluationError("FILE_TARGET_CONFLICT", "A criterion target is outside the evaluation scope.", "submission")
        names = set(targets)
    elif evaluator.maximum_files == 0:
        names = set()
    elif evaluator.uses_context_files or scoped is None:
        names = set(submission_files)
    else:
        names = scoped & submission_files.keys()

    def supported(name):
        if evaluator.file_extensions is not None:
            return PurePosixPath(name).suffix.lower() in evaluator.file_extensions
        if evaluator.source_files_only:
            expected = LANGUAGE_GRAMMARS.get(getattr(language, "value", language))
            grammar = source_grammar(name, language)
            return grammar is not None and (expected is None or grammar == expected)
        return True

    if targets is not None and any(not supported(name) for name in names):
        raise EvaluationError("UNSUPPORTED_FILE_TYPE", "A criterion target has an unsupported file type.", "submission")
    files = [submission_files[name] for name in sorted(names) if supported(name)]
    if len(files) < evaluator.minimum_files:
        raise EvaluationError("REQUIRED_FILE_MISSING", "A required assessment file is missing.", "submission")
    if evaluator.maximum_files is not None and len(files) > evaluator.maximum_files:
        raise EvaluationError("AMBIGUOUS_FILE_TARGET", "This assessment requires an explicit single file target.", "submission")
    return files
