import logging
from dataclasses import replace
from autograder.models.evaluation_error import EvaluationError

from autograder.models.abstract.step import Step
from autograder.models.dataclass.step_result import StepName, StepResult, StepStatus
from autograder.models.pipeline_execution import PipelineExecution
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
        pipeline_execution.definition_provenance = getattr(self, "definition_provenance", None)
        pipeline_execution.planned_steps = list(self._steps)
        pipeline_execution.capabilities = getattr(self, "capabilities", None)
        if hasattr(self, "definition"):
            from autograder.models.contracts.definition import select_language, DefinitionValidationError
            try:
                selected = select_language(self.definition, submission.language)
                submission = replace(submission, language=selected)
                pipeline_execution.submission = submission
                from autograder.models.capabilities import requirements_for
                requirements = requirements_for(self.compiled, selected)
                pipeline_execution.requirements = requirements
                pipeline_execution.planned_steps = [name for name in self._steps
                    if self._step_required(name, requirements)]
                # Pure validation deliberately precedes every provider/availability check.
                missing = set(requirements.preparation.required_files) - set(submission.submission_files)
                if missing:
                    raise EvaluationError("REQUIRED_FILE_MISSING", "A required submission file is missing.", "submission")
                from autograder.services.file_selection import select_files
                for category in (self.compiled.criteria_tree.base, self.compiled.criteria_tree.bonus,
                                 self.compiled.criteria_tree.penalty):
                    if category:
                        for test in category.get_all_tests():
                            select_files(test, submission.submission_files, submission.evaluation_scope, selected)
                self._check_capabilities(requirements.capabilities)
            except EvaluationError as exc:
                pipeline_execution.add_step_result(StepResult(
                    step=StepName.BOOTSTRAP, data=None, status=StepStatus.FAIL,
                    error=exc.message, error_code=exc.code, error_category=exc.category,
                    retryable=exc.retryable))
                pipeline_execution.finish_execution()
                return pipeline_execution
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
            pipeline_execution.planned_steps,
        )

        try:
            for step_name, step_instance in self._steps.items():
                if step_name not in pipeline_execution.planned_steps:
                    continue
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

    def _step_required(self, name, requirements):
        if name == StepName.SANDBOX:
            return "sandbox_execution" in requirements.capabilities
        if name == StepName.PRE_FLIGHT:
            return bool(requirements.preparation.setup_commands or self.definition.preparation.fixtures
                        or "http_network" in requirements.capabilities)
        if name == StepName.AI_BATCH:
            return "ai_provider" in requirements.capabilities
        return True

    def _check_capabilities(self, required):
        providers = self.capabilities
        if "http_network" in required and providers.server_execution is None:
            raise EvaluationError("SERVER_CAPABILITY_UNAVAILABLE",
                                  "This host cannot start and reach an assessed server.", "capability")
        if "sandbox_execution" in required and "http_network" not in required and providers.execution is None:
            raise EvaluationError("CAPABILITY_UNAVAILABLE", "The execution environment is unavailable.", "capability")
        if "fixture_provider" in required and providers.fixtures is None:
            raise EvaluationError("FIXTURE_PROVIDER_UNAVAILABLE", "The fixture provider is unavailable.", "capability")
        if "ai_provider" in required and providers.ai is None:
            raise EvaluationError("PROVIDER_UNAVAILABLE", "The assessment provider is unavailable.", "provider")

    def _cleanup_sandbox(self, pipeline_execution: PipelineExecution) -> None:
        """Close only this run's owned session before finalizing its outcome."""
        session = pipeline_execution.sandbox
        pipeline_execution.sandbox = None
        if session is not None:
            try:
                session.close()
            except Exception:
                logger.exception("Execution session cleanup failed (execution_id=%s)", pipeline_execution.execution_id)


def build_pipeline(*, definition, locale="en", provenance=None, templates=None, capabilities=None) -> AutograderPipeline:
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
    from autograder.models.capabilities import HostCapabilities
    pipeline.capabilities = capabilities or HostCapabilities()
    pipeline.compiled = compiled
    pipeline.definition = normalized
    pipeline.definition_provenance = provenance or DefinitionProvenance(definition_hash=compiled.definition_hash)
    if pipeline.definition_provenance.definition_hash != compiled.definition_hash:
        raise ValueError("Provenance hash must identify the compiled definition")
    config = {
        "include_feedback": normalized.feedback.enabled,
        "grading_criteria": normalized.criteria.model_dump(mode="json"),
        "feedback_config": normalized.feedback.preferences.model_dump(mode="json"),
        "preparation": normalized.preparation,
        "feedback_mode": normalized.feedback.mode,
        "locale": locale,
        "compiled_tree": compiled.criteria_tree,
    }
    registry = StepRegistry(config, templates=compiled.templates)
    for step_name in [StepName.LOAD_TEMPLATE, StepName.BUILD_TREE, StepName.SANDBOX,
                      StepName.PRE_FLIGHT, StepName.AI_BATCH,
                      StepName.GRADE, StepName.FOCUS, StepName.FEEDBACK]:
        step = BuildTreeStep(compiled.criteria_tree) if step_name == StepName.BUILD_TREE else registry.build_step(step_name)
        if step is not None:
            pipeline.add_step(step_name, step)
    return pipeline
