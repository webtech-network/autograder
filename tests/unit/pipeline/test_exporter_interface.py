import pytest
from unittest.mock import MagicMock, patch
from typing import Optional

from autograder.models.abstract.exporter import Exporter
from autograder.steps.export_step import ExporterStep
from autograder.services.upstash_driver import UpstashDriver
from github_action.github_classroom_exporter import GithubClassroomExporter
from autograder.steps.step_registry import StepRegistry
from autograder.models.dataclass.step_result import StepName, StepStatus


class MockExporter(Exporter):
    def __init__(self):
        self.called_with = None

    def export(self, user_id: str, score: float, feedback: Optional[str] = None) -> None:
        self.called_with = (user_id, score, feedback)


class TestExporterInterface:
    def test_exporter_step_calls_export(self):
        """ExporterStep calls export() on the injected Exporter with correct arguments."""
        mock_exporter = MockExporter()
        step = ExporterStep(mock_exporter)

        # Mock pipeline execution
        mock_exec = MagicMock()
        mock_exec.submission.user_id = "user123"
        mock_exec.get_grade_step_result.return_value.final_score = 85.0
        mock_exec.get_feedback.return_value = "Great work!"

        result_exec = step._execute(mock_exec)

        assert mock_exporter.called_with == ("user123", 85.0, "Great work!")
        
        # Verify result was added to pipeline
        mock_exec.add_step_result.assert_called_once()
        step_result = mock_exec.add_step_result.call_args[0][0]
        assert step_result.step == StepName.EXPORTER
        assert step_result.status == StepStatus.SUCCESS

    def test_upstash_driver_export_delegates(self):
        """UpstashDriver.export() delegates to set_score()."""
        with patch("autograder.services.upstash_driver.Redis"):
            driver = UpstashDriver()
            driver.set_score = MagicMock()
            
            driver.export("user123", 95.0, "Optional feedback")
            
            driver.set_score.assert_called_once_with("user123", 95.0)

    def test_github_classroom_exporter_export_delegates(self):
        """GithubClassroomExporter.export() delegates to GithubActionService.export_results()."""
        mock_service = MagicMock()
        exporter = GithubClassroomExporter(mock_service)
        
        exporter.export("user123", 70.0, "Need improvement")
        
        mock_service.export_results.assert_called_once_with(70.0, True, "Need improvement")

    def test_step_registry_build_exporter_none(self):
        """StepRegistry._build_exporter() returns None when export_results=False."""
        registry = StepRegistry({"export_results": False})
        step = registry._build_exporter()
        assert step is None

    def test_step_registry_build_exporter_injected(self):
        """StepRegistry._build_exporter() uses injected exporter when provided."""
        mock_exporter = MagicMock(spec=Exporter)
        registry = StepRegistry({"export_results": True, "exporter": mock_exporter})
        
        step = registry._build_exporter()
        assert isinstance(step, ExporterStep)
        assert step._exporter_service is mock_exporter

    def test_step_registry_build_exporter_default(self):
        """StepRegistry._build_exporter() creates UpstashDriver instance as default."""
        with patch("autograder.steps.step_registry.UpstashDriver") as mock_driver_cls:
            mock_driver = MagicMock(spec=UpstashDriver)
            mock_driver_cls.return_value = mock_driver
            
            registry = StepRegistry({"export_results": True})
            step = registry._build_exporter()
            
            assert isinstance(step, ExporterStep)
            assert step._exporter_service is mock_driver
            mock_driver_cls.assert_called_once()
