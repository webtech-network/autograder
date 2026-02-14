from autograder.models.abstract.step import Step
from autograder.models.dataclass.step_result import StepName
from autograder.models.pipeline_execution import PipelineExecution, PipelineStatus
from autograder.services.focus_service import FocusService
from autograder.services.report.reporter_service import ReporterService
from autograder.services.upstash_driver import UpstashDriver
from autograder.steps.export_step import ExporterStep
from autograder.steps.feedback_step import FeedbackStep
from autograder.steps.focus_step import FocusStep
from autograder.steps.grade_step import GradeStep
from autograder.steps.load_template_step import TemplateLoaderStep
from autograder.steps.pre_flight_step import PreFlightStep
from autograder.steps.build_tree_step import BuildTreeStep
from autograder.models.dataclass.submission import Submission


class AutograderPipeline:
    """
    AutograderPipeline orchestrates the execution of steps for grading a submission.

        The pipeline is designed to be flexible and configurable, allowing for different grading workflows based on the provided configuration.
        It holds a PipelineExecution object that keeps all the execution footprint, including the original submission, intermediate results from each step, and the final grading result.
    """

    def __init__(self):
        """
        Initializes the AutograderPipeline with an empty steps dictionary.
         The steps will be added in the order they should be executed.
         Each step is identified by a unique StepName.
         The pipeline execution will pass a PipelineExecution object through each step, allowing them to share data and results.
         The pipeline handles execution flow, error handling, and finalization of the grading process.
        """
        self._steps = {}

    def add_step(self, step_name: StepName, step: Step) -> None:
        self._steps[step_name] = step

    def run(self, submission: Submission):
        """
        Run the autograder pipeline on a given submission.
        Args:
            submission: The submission to be graded, containing all necessary data for grading.
        Returns:
            PipelineExecution object containing the results of the grading process, including final score, feedback, and any errors encountered during execution.

        """
        pipeline_execution = PipelineExecution.start_execution(submission)

        for step in self._steps:
            print("Executing step:", step)  # TODO: Replace with proper logging

            try:
                pipeline_execution = self._steps[step].execute(pipeline_execution)
                # Check if the step that just executed failed
                current_step_result = pipeline_execution.get_previous_step()
                if current_step_result and not current_step_result.is_successful:
                    pipeline_execution.set_failure()
                    print(f"Step {step} failed: {current_step_result.error}")  # TODO: Replace with proper logging
                    break
            except Exception as e:
                pipeline_execution.status = PipelineStatus.INTERRUPTED
                print(
                    f"Error executing step {step}: {str(e)}"
                )  # TODO: Replace with proper logging
                break

        pipeline_execution.finish_execution() # Generates GradingResult object in pipeline execution

        # Cleanup: Release sandbox back to pool if it was created
        self._cleanup_sandbox(pipeline_execution)

        return pipeline_execution

    def _cleanup_sandbox(self, pipeline_execution: PipelineExecution) -> None:
        """Release sandbox back to pool after pipeline execution."""
        try:
            if pipeline_execution.has_step_result(StepName.PRE_FLIGHT):
                from sandbox_manager.manager import get_sandbox_manager

                preflight_result = pipeline_execution.get_step_result(StepName.PRE_FLIGHT)
                sandbox = preflight_result.data

                if sandbox:  # Only if a sandbox was created
                    manager = get_sandbox_manager()
                    language = pipeline_execution.submission.language
                    manager.release_sandbox(language, sandbox)
        except Exception as e:
            # Log error but don't fail the pipeline
            print(f"Warning: Failed to cleanup sandbox: {str(e)}")


def build_pipeline(
    template_name,
    include_feedback,
    grading_criteria,
    feedback_config,
    setup_config=None,
    custom_template=None,
    feedback_mode=None,
    export_results=False,
) -> AutograderPipeline:
    """
    Build the AutograderPipeline object based on configuration.

    Args:
        template_name: Name of the template to use
        include_feedback: Whether to include feedback generation
        grading_criteria: Criteria configuration dictionary
        feedback_config: Configuration for feedback generation
        setup_config: Pre-flight setup configuration
        custom_template: Custom template object (if any)
        feedback_mode: Mode for feedback generation (default or ai)
    Returns:
        Configured AutograderPipeline object ready to run with submissions
    """
    pipeline = AutograderPipeline()

    # Load template
    pipeline.add_step(
        StepName.LOAD_TEMPLATE, TemplateLoaderStep(template_name, custom_template)
    )  # Passes the template to the next step

    pipeline.add_step(
        StepName.BUILD_TREE, BuildTreeStep(grading_criteria)
    )  # Uses template to match selected tests in criteria and builds tree

    # Run pre-flight if setup_config is provided (even if empty), as the step will create sandbox if template requires it
    if setup_config is not None:
        pipeline.add_step(StepName.PRE_FLIGHT, PreFlightStep(setup_config))

    pipeline.add_step(
        StepName.GRADE, GradeStep()
    )  # Generates GradingResult with final score and result tree

    # Feedback generation (if configured)
    if include_feedback:
        focus_service = FocusService()
        pipeline.add_step(StepName.FOCUS, FocusStep(focus_service))

        reporter_service = ReporterService(feedback_mode=feedback_mode)
        pipeline.add_step(
            StepName.FEEDBACK, FeedbackStep(reporter_service, feedback_config)
        )  # Uses GradingResult to generate feedback and appends it to GradingResult

    # Export results
    if export_results:
        pipeline.add_step(
            StepName.EXPORTER, ExporterStep(UpstashDriver)
        )  # Exports final results and feedback to external system

    return pipeline
