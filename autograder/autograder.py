import logging
from dataclasses import replace

from autograder.models.abstract.step import Step
from autograder.models.dataclass.step_result import StepName, StepResult, StepStatus
from autograder.models.pipeline_execution import PipelineExecution, PipelineStatus
from autograder.steps.step_registry import StepRegistry
from autograder.models.dataclass.submission import Submission
from autograder.services.template_library_service import TemplateLibraryService

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
        pipeline_execution.definition_provenance = getattr(self, "definition_provenance", None)
        pipeline_execution.planned_steps = list(self._steps)
        if hasattr(self, "definition"):
            from autograder.models.contracts.definition import select_language, DefinitionValidationError
            try:
                selected = select_language(self.definition, submission.language)
                submission = replace(submission, language=selected)
                pipeline_execution.submission = submission
            except DefinitionValidationError as exc:
                error = exc.errors()[0]
                pipeline_execution.add_step_result(StepResult(
                    step=StepName.BOOTSTRAP, data=None, status=StepStatus.FAIL,
                    error="The submission language is not valid for this definition.",
                    error_code=error["code"], error_category="submission"))
                pipeline_execution.finish_execution()
                return pipeline_execution

        logger.info(
            "Pipeline started: external_user_id=%s, assignment_id=%s, language=%s, steps=%s",
            submission.user_id,
            submission.assignment_id,
            submission.language.value if submission.language else "none",
            list(self._steps.keys()),
        )

        try:
            for step_name, step_instance in self._steps.items():
                logger.info("Executing step: %s (external_user_id=%s)", step_name, submission.user_id)
                try:
                    returned = step_instance.execute(pipeline_execution)
                    if returned is not pipeline_execution:
                        raise RuntimeError("Steps must return their existing execution context")
                except Exception:  # A custom step may bypass the standard wrapper.
                    logger.exception("Unhandled exception in step %s", step_name)
                    pipeline_execution.add_step_result(StepResult(
                        step=step_name, data=None, status=StepStatus.INTERRUPTED,
                        error="The grading execution could not complete.", error_code="EXECUTION_ERROR"))
                current_step_result = pipeline_execution.get_previous_step()
                if current_step_result and not current_step_result.is_successful:
                    pipeline_execution.set_failure()
                    # Feedback and focus are optional enrichment; continue only if
                    # later enrichment can operate independently of the failure.
                    if step_name == StepName.FEEDBACK:
                        continue
                    break
        finally:
            self._cleanup_sandbox(pipeline_execution)
        try:
            pipeline_execution.finish_execution()
        except Exception:
            logger.exception("Invalid final grading assessment")
            pipeline_execution.add_step_result(StepResult(
                step=StepName.GRADE, data=None, status=StepStatus.INTERRUPTED,
                error="The grading execution produced an invalid assessment.",
                error_code="INVALID_EVALUATOR_RESULT"))
            pipeline_execution.set_failure()
            pipeline_execution.finish_execution()

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
        except Exception as e:  # pylint: disable=broad-exception-caught
            # Log error but don't fail the pipeline
            logger.warning(
                "Failed to cleanup sandbox (external_user_id=%s): %s",
                pipeline_execution.submission.user_id,
                str(e),
            )


def build_pipeline(*, definition, locale="en", provenance=None, templates=None) -> AutograderPipeline:
    """Compile the single public contract before constructing execution steps.

    Trusted Python templates may be supplied as an identifier-to-Template map.
    Publication and provider credentials belong to the caller.
    """
    from autograder.models.contracts.definition import compile_definition
    from autograder.models.contracts.provenance import DefinitionProvenance
    from autograder.steps.build_tree_step import BuildTreeStep
    compiled = compile_definition(definition, templates=templates)
    normalized = compiled.definition
    pipeline = AutograderPipeline()
    pipeline.definition = normalized
    pipeline.definition_provenance = provenance or DefinitionProvenance(definition_hash=compiled.definition_hash)
    if pipeline.definition_provenance.definition_hash != compiled.definition_hash:
        raise ValueError("Provenance hash must identify the compiled definition")
    config = {
        "include_feedback": normalized.feedback.enabled,
        "grading_criteria": normalized.criteria.model_dump(mode="json"),
        "feedback_config": normalized.feedback.preferences.model_dump(mode="json"),
        "setup_config": normalized.preparation.runtime_setup() or None,
        "feedback_mode": normalized.feedback.mode,
        "locale": locale,
        "compiled_tree": compiled.criteria_tree,
    }
    registry = StepRegistry(config, templates=compiled.templates)
    for step_name in [StepName.LOAD_TEMPLATE, StepName.BUILD_TREE, StepName.SANDBOX,
                      StepName.PRE_FLIGHT, StepName.AI_BATCH, StepName.STRUCTURAL_ANALYSIS,
                      StepName.GRADE, StepName.FOCUS, StepName.FEEDBACK]:
        step = BuildTreeStep(compiled.criteria_tree) if step_name == StepName.BUILD_TREE else registry.build_step(step_name)
        if step is not None:
            pipeline.add_step(step_name, step)
    return pipeline
