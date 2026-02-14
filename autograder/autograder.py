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

    def run(self, submission: "Submission"):
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

            if not pipeline_execution.get_previous_step.is_successful:
                pipeline_execution.set_failure()
                break
            try:
                pipeline_execution = self._steps[step].execute(pipeline_execution)
            except Exception as e:
                pipeline_execution.status = PipelineStatus.INTERRUPTED
                print(
                    f"Error executing step {step}: {str(e)}"
                )  # TODO: Replace with proper logging
                break

        pipeline_execution.finish_execution()  # Generates GradingResult object in pipeline execution
        return pipeline_execution


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

    # Pre-flight checks (if configured)
    if setup_config:
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
