"""Regression coverage for rich per-file metadata passthrough."""

from copy import deepcopy
from unittest.mock import Mock, patch

import pytest

from autograder.models.abstract.test_function import TestFunction
from autograder.models.criteria_tree import CategoryNode, CriteriaTree, TestNode
from autograder.models.dataclass.test_result import TestResult
from autograder.services.grader.grader_service import GraderService
from web.service.grading_service import GradingRequest, _run_pipeline


class MetadataCapturingTest(TestFunction):
    """Test function that records the files and context received by the grader."""

    def __init__(self):
        self.files = None
        self.kwargs = None

    @property
    def name(self) -> str:
        return "metadata_capture"

    @property
    def description(self) -> str:
        return "Capture opaque per-file metadata."

    @property
    def parameter_description(self) -> list:
        return []

    def execute(self, files, sandbox, *args, **kwargs) -> TestResult:
        self.files = files
        self.kwargs = kwargs
        return TestResult(
            test_name=self.name,
            score=100.0,
            report="Metadata received.",
        )


@pytest.mark.asyncio
async def test_rich_repository_metadata_survives_hydration_and_grader_passthrough():
    """Nested repository context remains opaque, unchanged, and correctly targeted."""
    repository_file_metadata = {
        "provider": "github",
        "change_status": "modified",
        "patch": "@@ -88,6 +88,12 @@ class PaymentService:",
        "blob": {
            "sha": "f00ba4",
            "url": "https://example.invalid/blob/f00ba4",
        },
        "stats": {
            "additions": 12,
            "deletions": 3,
            "changes": 15,
        },
        "review": {
            "labels": ["backend", "security"],
            "requested_reviewers": ["alice", "bob"],
            "approved": False,
        },
        "annotations": [
            {"line": 91, "kind": "security-sensitive"},
            {"line": 95, "kind": "new-branch"},
        ],
        "optional_context": None,
    }
    other_file_metadata = {
        "provider": "github",
        "change_status": "added",
    }
    stored_submission_files = {
        "service/payment.py": {
            "filename": "service/payment.py",
            "content": "class PaymentService:\n    pass\n",
            "changed_lines": [1, 2],
            "file_metadata": repository_file_metadata,
        },
        "README.md": {
            "filename": "README.md",
            "content": "# Payment service\n",
            "changed_lines": [1],
            "file_metadata": other_file_metadata,
        },
    }
    original_stored_data = deepcopy(stored_submission_files)
    request = GradingRequest(
        submission_id=10,
        grading_config_id=20,
        template_name="static_analysis",
        criteria_config={"base": {}},
        setup_config={},
        feedback_config={},
        include_feedback=False,
        language="python",
        username="repository-user",
        external_user_id="external-user",
        submission_files=stored_submission_files,
        evaluation_scope={"scoped_files": ["service/payment.py"]},
    )
    pipeline = Mock()
    pipeline.run.side_effect = lambda submission: submission

    with patch(
        "web.service.grading_service.build_pipeline",
        return_value=pipeline,
    ):
        hydrated_submission = await _run_pipeline(request)

    capturing_test = MetadataCapturingTest()
    criteria_tree = CriteriaTree(
        base=CategoryNode(
            name="base",
            weight=100,
            tests=[
                TestNode(
                    name="metadata_capture",
                    test_function=capturing_test,
                    file_target=["service/payment.py"],
                )
            ],
        )
    )

    GraderService().grade_from_tree(
        criteria_tree=criteria_tree,
        submission_files=hydrated_submission.submission_files,
        evaluation_scope=hydrated_submission.evaluation_scope,
    )

    assert stored_submission_files == original_stored_data
    assert hydrated_submission.evaluation_scope.scoped_files == [
        "service/payment.py"
    ]

    target_file = hydrated_submission.submission_files["service/payment.py"]
    assert target_file.changed_lines == {1, 2}
    assert target_file.metadata == repository_file_metadata
    assert target_file.metadata is repository_file_metadata

    assert capturing_test.files == [target_file]
    assert capturing_test.kwargs["evaluation_scope"] is hydrated_submission.evaluation_scope
    assert capturing_test.kwargs["file_metadata"] == {
        "service/payment.py": repository_file_metadata,
    }
    assert capturing_test.kwargs["file_metadata"]["service/payment.py"] is (
        repository_file_metadata
    )
    assert "README.md" not in capturing_test.kwargs["file_metadata"]
