from typing import Dict, Callable, Any, Optional

from autograder.models.dataclass.step_result import StepName
from autograder.models.abstract.step import Step

# Imports of all steps
from autograder.steps.load_template_step import TemplateLoaderStep
from autograder.steps.build_tree_step import BuildTreeStep
from autograder.steps.pre_flight_step import PreFlightStep
from autograder.steps.sandbox_step import SandboxStep
from autograder.steps.grade_step import GradeStep
from autograder.steps.focus_step import FocusStep
from autograder.steps.feedback_step import FeedbackStep
from autograder.steps.export_step import ExporterStep

from autograder.services.focus_service import FocusService
from autograder.services.report.reporter_service import ReporterService
from autograder.services.upstash_driver import UpstashDriver


class StepRegistry:
    """
    Factory pattern for creating pipeline steps based on a specific configuration.
    It encapsulates conditional logic for optional steps.
    """
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the step registry with a pipeline configuration dict.
        """
        self.config = config
        
        self._builders: Dict[StepName, Callable[[], Optional[Step]]] = {
            StepName.LOAD_TEMPLATE: self._build_load_template,
            StepName.BUILD_TREE: self._build_build_tree,
            StepName.PRE_FLIGHT: self._build_pre_flight,
            StepName.SANDBOX: self._build_sandbox,
            StepName.GRADE: self._build_grade,
            StepName.FOCUS: self._build_focus,
            StepName.FEEDBACK: self._build_feedback,
            StepName.EXPORTER: self._build_exporter,
        }

    def _build_load_template(self) -> Optional[Step]:
        template_name = self.config.get("template_name")
        custom_template = self.config.get("custom_template")
        return TemplateLoaderStep(template_name, custom_template)

    def _build_build_tree(self) -> Optional[Step]:
        return BuildTreeStep(self.config.get("grading_criteria"))

    def _build_pre_flight(self) -> Optional[Step]:
        setup_config = self.config.get("setup_config")
        if setup_config is not None:
            return PreFlightStep(setup_config)
        return None

    def _build_sandbox(self) -> Optional[Step]:
        setup_config = self.config.get("setup_config")
        if setup_config is not None:
            return SandboxStep(setup_config)
        return None

    def _build_grade(self) -> Optional[Step]:
        return GradeStep()

    def _build_focus(self) -> Optional[Step]:
        return FocusStep(FocusService())

    def _build_feedback(self) -> Optional[Step]:
        if self.config.get("include_feedback"):
            feedback_mode = self.config.get("feedback_mode")
            feedback_config = self.config.get("feedback_config")
            return FeedbackStep(ReporterService(feedback_mode=feedback_mode), feedback_config)
        return None

    def _build_exporter(self) -> Optional[Step]:
        if self.config.get("export_results"):
            return ExporterStep(UpstashDriver)
        return None

    def build_step(self, step_name: StepName) -> Optional[Step]:
        """
        Builds a step instance dynamically.
        Returns None if the step is optional and should not be included based on configuration.
        """
        builder = self._builders.get(step_name)
        if not builder:
            raise ValueError(f"No builder registered for step {step_name}")
        return builder()
