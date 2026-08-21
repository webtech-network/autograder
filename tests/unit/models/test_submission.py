"""Tests for submission evaluation context models."""

from autograder.models.dataclass.submission import (
    EvaluationScope,
    Submission,
    SubmissionFile,
)


def test_submission_file_context_is_optional():
    """Snapshot submissions retain their context-free defaults."""
    sub_file = SubmissionFile(filename="main.py", content="print('hello')")

    assert sub_file.changed_lines is None
    assert sub_file.metadata is None
    assert sub_file.is_contribution_aware is False


def test_submission_file_reports_changed_line_context():
    """Supplying even an empty changed-line set makes the file context-aware."""
    sub_file = SubmissionFile(
        filename="main.py",
        content="print('hello')",
        changed_lines=set(),
        metadata={"change_status": "modified"},
    )

    assert sub_file.is_contribution_aware is True
    assert sub_file.metadata == {"change_status": "modified"}


def test_submission_evaluation_scope_is_optional():
    """Evaluation scope is additive and available through the submission."""
    submission = Submission(
        username="student",
        user_id=1,
        assignment_id=2,
        submission_files={},
    )
    assert submission.evaluation_scope is None

    scope = EvaluationScope(scoped_files=["main.py"])
    submission.evaluation_scope = scope
    assert submission.evaluation_scope is scope
