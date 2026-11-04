"""One assessment-file policy for ordinary and AI criteria.

Files outside the assessment remain available as context and sandbox input.
"""
from typing import Dict, List, Optional

from autograder.models.criteria_tree import TestNode
from autograder.models.dataclass.submission import EvaluationScope, SubmissionFile
from autograder.models.evaluation_error import EvaluationError



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

    # File types are the evaluator's decision (its parser rules), not a language table.
    if targets is not None and any(not evaluator.accepts_file(name, language) for name in names):
        raise EvaluationError("UNSUPPORTED_FILE_TYPE", "A criterion target has an unsupported file type.", "submission")
    files = [submission_files[name] for name in sorted(names) if evaluator.accepts_file(name, language)]
    if len(files) < evaluator.minimum_files:
        raise EvaluationError("REQUIRED_FILE_MISSING", "A required assessment file is missing.", "submission")
    if evaluator.maximum_files is not None and len(files) > evaluator.maximum_files:
        raise EvaluationError("AMBIGUOUS_FILE_TARGET", "This assessment requires an explicit single file target.", "submission")
    return files
