import pytest
from unittest.mock import MagicMock, patch
from autograder.models.dataclass.submission import Submission
from autograder.models.pipeline_execution import PipelineExecution
from autograder.steps.pre_flight_step import PreFlightStep
from sandbox_manager.sandbox_container import SandboxContainer
from sandbox_manager.models.sandbox_models import Language

class TestPreFlightAssetIntegration:
    @patch('autograder.services.assets.resolver.S3AssetProvider')
    def test_pre_flight_step_injects_assets(self, mock_s3_provider_cls):
        # Mock S3 provider to return tar content
        mock_s3_provider = mock_s3_provider_cls.return_value
        mock_s3_provider.get_asset_tar.return_value = b"mock_tar_content"
        
        # Setup configuration with assets
        setup_config = {
            "assets": [
                {
                    "source": "data.csv",
                    "target": "/tmp/data.csv",
                    "read_only": True
                }
            ]
        }
        
        step = PreFlightStep(setup_config)
        
        # Create a pipeline execution with a mock sandbox
        submission = Submission(
            username="testuser",
            user_id=1,
            assignment_id=1,
            submission_files={},
            language=Language.PYTHON
        )
        pipeline_exec = PipelineExecution.start_execution(submission)
        
        # Mock sandbox and attach it to pipeline
        mock_container_ref = MagicMock()
        sandbox = SandboxContainer(Language.PYTHON, mock_container_ref)
        pipeline_exec.sandbox = sandbox
        
        # Execute the step
        step._execute(pipeline_exec)
        
        # Verify asset resolution was called
        mock_s3_provider.get_asset_tar.assert_called_once_with("data.csv", "/tmp/data.csv", True)
        
        # Verify injection was called on container
        mock_container_ref.put_archive.assert_called_once_with(
            path='/',
            data=b"mock_tar_content"
        )
        
        # Verify mkdir -p was called for parent dir
        mock_container_ref.exec_run.assert_any_call(
            cmd="mkdir -p /tmp",
            user="root"
        )
