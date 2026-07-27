import logging
from typing import Dict, Callable, Any, Optional, List

from autograder.models.dataclass.step_result import StepName
from autograder.models.abstract.step import Step

# Imports of all steps
from autograder.steps.load_template_step import TemplateLoaderStep
from autograder.steps.build_tree_step import BuildTreeStep
from autograder.steps.pre_flight_step import PreFlightStep
from autograder.steps.sandbox_step import SandboxStep
from autograder.steps.ai_batch_step import AiBatchStep
from autograder.steps.structural_analysis_step import StructuralAnalysisStep
from autograder.steps.grade_step import GradeStep
from autograder.steps.focus_step import FocusStep
from autograder.steps.feedback_step import FeedbackStep
from autograder.steps.export_step import ExporterStep

from autograder.services.focus_service import FocusService
from autograder.services.report.reporter_service import ReporterService


class StepRegistry:
    """
    Factory pattern for creating pipeline steps based on a specific configuration.
    It encapsulates conditional logic for optional steps.
    """
    def __init__(self, config: Dict[str, Any], templates: Optional[List[Any]] = None):
        """
        Initialize the step registry with a pipeline configuration dict.
        """
        self.config = config
        self.templates = templates or []
        
        self._builders: Dict[StepName, Callable[[], Optional[Step]]] = {
            StepName.LOAD_TEMPLATE: self._build_load_template,
            StepName.BUILD_TREE: self._build_build_tree,
            StepName.PRE_FLIGHT: self._build_pre_flight,
            StepName.SANDBOX: self._build_sandbox,
            StepName.AI_BATCH: self._build_ai_batch,
            StepName.STRUCTURAL_ANALYSIS: self._build_structural_analysis,
            StepName.GRADE: self._build_grade,
            StepName.FOCUS: self._build_focus,
            StepName.FEEDBACK: self._build_feedback,
            StepName.EXPORTER: self._build_exporter,
        }

    def _build_load_template(self) -> Optional[Step]:
        template_name = self.config.get("template_name")
        custom_template = self.config.get("custom_template")
        return TemplateLoaderStep(template_name, custom_template, templates=self.templates)

    def _build_build_tree(self) -> Optional[Step]:
        return BuildTreeStep(self.config.get("grading_criteria"))

    def _build_pre_flight(self) -> Optional[Step]:
        # Only return PreFlightStep if there is a setup_config to process.
        setup_config = self.config.get("setup_config")
        if not setup_config:
            return None
        return PreFlightStep(setup_config)

    def _build_sandbox(self) -> Optional[Step]:
        # Only return SandboxStep if at least one template requires it.
        if not any(t.requires_sandbox for t in self.templates):
            return None
        return SandboxStep()

    def _build_ai_batch(self) -> Optional[Step]:
        # Check if any of the loaded templates have AI test functions, or if the criteria tree
        # (not yet built, but we can look at the config) suggests AI tests.
        # For simplicity and correctness, we check the templates first.
        from autograder.models.abstract.ai_test_function import AiTestFunction
        
        has_ai_tests = False
        for template in self.templates:
            if any(isinstance(tf, AiTestFunction) for tf in template.get_tests().values()):
                has_ai_tests = True
                break
        
        if not has_ai_tests:
            return None

        return AiBatchStep()

    def _build_structural_analysis(self) -> Optional[Step]:
        return StructuralAnalysisStep()

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
            exporter = self.config.get("exporter")
            if exporter is None:
                raise ValueError(
                    "export_results=True requires an 'exporter' to be provided to build_pipeline(). "
                    "Pass an Exporter instance (e.g. UpstashDriver, CloudExporter) via the exporter= argument."
                )
            return ExporterStep(exporter)
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
