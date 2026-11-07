"""One assessment-file policy for ordinary and AI criteria.

Files outside the assessment remain available as context and sandbox input.
"""
from typing import Dict, List, Optional

from autograder.models.criteria_tree import TestNode
from autograder.models.dataclass.submission import EvaluationScope, SubmissionFile
from autograder.models.evaluation_error import EvaluationError


def _explained(code: str, message: str, key: str, test: TestNode, *, files=(), **params) -> EvaluationError:
    """A submission failure naming the criterion and, when relevant, its files (see OUTCOMES.md)."""
    return EvaluationError(code, message, "submission", explanation=(
        key, {"criterion": test.name, "files": ", ".join(files), **params}))


def select_files(
    test: TestNode,
    submission_files: Dict[str, SubmissionFile],
    scope: Optional[EvaluationScope] = None,
    language=None,
) -> List[SubmissionFile]:
    """Resolve and validate every selected criterion without dropping it from the tree."""
    evaluator = test.test_function
    targets = test.file_target
    scoped = set(scope.scoped_files) if scope is not None else None
    if targets is not None:
        missing = [name for name in targets if name not in submission_files]
        if missing:
            raise _explained("REQUIRED_FILE_MISSING", "A required assessment file is missing.",
                             "preflight.error.target_file_missing", test, files=missing)
        if scoped is not None and not set(targets).issubset(scoped):
            raise _explained("FILE_TARGET_CONFLICT", "A criterion target is outside the evaluation scope.",
                             "preflight.error.target_outside_scope", test, files=[name for name in targets if name not in scoped])
        names = set(targets)
    elif evaluator.maximum_files == 0:
        names = set()
    elif evaluator.uses_context_files or scoped is None:
        names = set(submission_files)
    else:
        names = scoped & submission_files.keys()

    # File types are the evaluator's decision (its parser rules), not a language table.
    unsupported = sorted(name for name in names if not evaluator.accepts_file(name, language)) if targets is not None else []
    if unsupported:
        raise _explained("UNSUPPORTED_FILE_TYPE", "A criterion target has an unsupported file type.",
                         "preflight.error.unsupported_file_type", test, files=unsupported)
    files = [submission_files[name] for name in sorted(names) if evaluator.accepts_file(name, language)]
    if len(files) < evaluator.minimum_files:
        raise _explained("REQUIRED_FILE_MISSING", "A required assessment file is missing.",
                         "preflight.error.too_few_files", test, minimum=evaluator.minimum_files, found=len(files))
    if evaluator.maximum_files is not None and len(files) > evaluator.maximum_files:
        raise _explained("AMBIGUOUS_FILE_TARGET", "This assessment requires an explicit single file target.",
                         "preflight.error.ambiguous_file_target", test, maximum=evaluator.maximum_files, found=len(files))
    return files
