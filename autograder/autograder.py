import logging

from autograder.models.abstract.step import Step
from autograder.models.dataclass.step_result import StepName
from autograder.models.pipeline_execution import PipelineExecution, PipelineStatus
from autograder.steps.step_registry import StepRegistry
from autograder.models.dataclass.submission import Submission

logger = logging.getLogger(__name__)


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
        """
        Adds a grading step to the pipeline.

        Args:
            step_name: The unique identifier for the step.
            step: The Step instance to be executed.
        """
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

        logger.info(
            "Pipeline started: external_user_id=%s, assignment_id=%s, language=%s, steps=%s",
            submission.user_id,
            submission.assignment_id,
            submission.language.value if submission.language else "none",
            list(self._steps.keys()),
        )

        for step_name, step_instance in self._steps.items():
            logger.info("Executing step: %s (external_user_id=%s)", step_name, submission.user_id)

            try:
                pipeline_execution = step_instance.execute(pipeline_execution)
                # Check if the step that just executed failed
                current_step_result = pipeline_execution.get_previous_step()
                if current_step_result and not current_step_result.is_successful:
                    pipeline_execution.set_failure()
                    logger.warning(
                        "Step %s failed: %s (external_user_id=%s)",
                        step_name,
                        current_step_result.error,
                        submission.user_id,
                    )
                    break
                logger.info("Step %s completed successfully (external_user_id=%s)", step_name, submission.user_id)
            except Exception as e:
                pipeline_execution.status = PipelineStatus.INTERRUPTED
                logger.error(
                    "Unhandled exception in step %s (external_user_id=%s): %s",
                    step_name,
                    submission.user_id,
                    str(e),
                    exc_info=True,
                )
                break

        pipeline_execution.finish_execution() # Generates GradingResult object in pipeline execution

        # Cleanup: Destroy sandbox if it was created
        self._cleanup_sandbox(pipeline_execution)

        logger.info(
            "Pipeline finished: external_user_id=%s, status=%s",
            submission.user_id,
            pipeline_execution.status,
        )

        return pipeline_execution

    def _cleanup_sandbox(self, pipeline_execution: PipelineExecution) -> None:
        """Destroy sandbox after pipeline execution to avoid cross-submission reuse."""
        try:
            sandbox = pipeline_execution.sandbox
            if sandbox:
                from sandbox_manager.manager import get_sandbox_manager
                manager = get_sandbox_manager()
                language = pipeline_execution.submission.language
                manager.destroy_sandbox(language, sandbox)
                pipeline_execution.sandbox = None
                logger.info(
                    "Sandbox destroyed: external_user_id=%s, language=%s",
                    pipeline_execution.submission.user_id,
                    language.value if language else "none",
                )
        except Exception as e:
            # Log error but don't fail the pipeline
            logger.warning(
                "Failed to cleanup sandbox (external_user_id=%s): %s",
                pipeline_execution.submission.user_id,
                str(e),
            )


def build_pipeline(
    template_name,
    include_feedback,
    grading_criteria,
    feedback_config,
    setup_config=None,
    custom_template=None,
    feedback_mode=None,
    export_results=False,
    exporter=None,
    locale="en",
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

    config = {
        "template_name": template_name,
        "include_feedback": include_feedback,
        "grading_criteria": grading_criteria,
        "feedback_config": feedback_config,
        "setup_config": setup_config,
        "custom_template": custom_template,
        "feedback_mode": feedback_mode,
        "export_results": export_results,
        "exporter": exporter,
        "locale": locale,
    }
    registry = StepRegistry(config)

    execution_order = [
        StepName.LOAD_TEMPLATE,
        StepName.BUILD_TREE,
        StepName.SANDBOX,
        StepName.PRE_FLIGHT,
        StepName.AI_BATCH,
        StepName.STRUCTURAL_ANALYSIS,
        StepName.GRADE,
        StepName.FOCUS,
        StepName.FEEDBACK,
        StepName.EXPORTER,
    ]

    for step_name in execution_order:
        step_instance = registry.build_step(step_name)
        if step_instance is not None:
            pipeline.add_step(step_name, step_instance)

    
    
    return pipeline
