"""The ordered grading flow. Intermediate values never live in diagnostics."""
import logging
import time
from dataclasses import replace
from datetime import datetime, timezone
from uuid import uuid4

from pydantic import ValidationError

from autograder.models.capabilities import HostCapabilities, requirements_for
from autograder.models.contracts.definition import CompiledDefinition, compile_definition, select_language, DefinitionValidationError
from autograder.models.contracts.outcome import CompletedOutcome, FailedOutcome, FeedbackOutcome, OutcomeError, ResultOutcomeTree
from autograder.models.contracts.provenance import DefinitionProvenance
from autograder.models.dataclass.submission import Submission
from autograder.models.diagnostics import DiagnosticEvent, DiagnosticObserver
from autograder.models.evaluation_error import EvaluationError
from autograder.models.pipeline_execution import PipelineExecution
from autograder.services.ai_batch import evaluate_ai_batch
from autograder.services.focus_service import FocusService
from autograder.services.grader.grader_service import GraderService
from autograder.services.preparation import check_capabilities, prepare_session, validate_submission
from autograder.services.report.reporter_service import ReporterService

logger = logging.getLogger(__name__)


def _observe(observer: DiagnosticObserver | None, execution_id: str, operation: str,
             error: OutcomeError | None = None) -> None:
    if observer is None:
        return
    try:
        observer(DiagnosticEvent(execution_id, operation, "failed" if error else "completed", error))
    except Exception:  # pylint: disable=broad-exception-caught
        # A host's diagnostic consumer cannot invalidate or interrupt grading.
        logger.exception("Diagnostic observer failed (execution_id=%s)", execution_id)


def _outcome_error(error: EvaluationError, execution_id: str) -> OutcomeError:
    return OutcomeError(code=error.code, message=error.message, category=error.category,
                        retryable=error.retryable, correlation_id=execution_id)


class AutograderPipeline:
    """A compiled definition and borrowed host capabilities, reusable across runs."""

    def __init__(self, compiled: CompiledDefinition, provenance: DefinitionProvenance,
                 capabilities: HostCapabilities):
        self.compiled = compiled
        self.definition = compiled.definition
        self.definition_provenance = provenance
        self.capabilities = capabilities

    # Keep the ordered calls and failure boundaries together instead of hiding
    # them behind a configurable step framework.
    # pylint: disable=too-many-locals,too-many-branches,too-many-statements
    def run(self, submission: Submission, *, observer: DiagnosticObserver | None = None) -> PipelineExecution:
        """Return a finalized outcome after closing this run's owned session."""
        execution_id = str(uuid4())
        started_at = datetime.now(timezone.utc)
        started = time.monotonic()
        session = None
        tree = None
        error = None
        feedback = FeedbackOutcome()
        operation = "bind_submission"

        # Required work has one failure boundary. The local session is owned as
        # soon as acquisition returns, even if staging immediately raises.
        try:
            submission = replace(submission, language=select_language(self.definition, submission.language))
            requirements = requirements_for(self.compiled, submission.language)
            validate_submission(self.compiled, submission, requirements)
            check_capabilities(requirements.capabilities, self.capabilities)
            _observe(observer, execution_id, operation)

            if "sandbox_execution" in requirements.capabilities:
                operation = "open_session"
                acquire = (self.capabilities.server_execution if "http_network" in requirements.capabilities
                           else self.capabilities.execution)
                try:
                    session = acquire(submission.language)
                    session.prepare_workdir(submission.submission_files)
                except Exception as exc:
                    raise EvaluationError("CAPABILITY_UNAVAILABLE", "The execution environment is unavailable.", "capability", True) from exc
                _observe(observer, execution_id, operation)
                operation = "prepare_session"
                prepare_session(session, self.compiled, requirements, self.capabilities)
                _observe(observer, execution_id, operation)

            assessments = None
            if "ai_provider" in requirements.capabilities:
                operation = "evaluate_ai_batch"
                assessments = evaluate_ai_batch(self.compiled.criteria_tree, submission, self.capabilities.ai)
                _observe(observer, execution_id, operation)

            operation = "grade"
            result_tree = GraderService().grade_from_tree(
                criteria_tree=self.compiled.criteria_tree,
                submission_files=submission.submission_files, sandbox=session,
                submission_language=submission.language, locale=submission.locale,
                pre_computed_results=assessments, evaluation_scope=submission.evaluation_scope,
            )
            result_tree.calculate_final_score()
            try:
                tree = ResultOutcomeTree.model_validate(result_tree.root.to_dict())
            except (ValidationError, TypeError, ValueError) as exc:
                raise EvaluationError("INVALID_EVALUATOR_RESULT", "The grading execution produced an invalid assessment.", "internal") from exc
            _observe(observer, execution_id, operation)

            # Optional enrichment receives the completed grade directly. It
            # cannot replace that grade, and disabled feedback performs no work.
            if self.definition.feedback.enabled:
                operation = "feedback"
                try:
                    focus = FocusService().find(result_tree)
                    content = ReporterService(feedback_mode=self.definition.feedback.mode).generate_feedback(
                        grading_result=focus, result_tree=result_tree,
                        feedback_config=self.definition.feedback.preferences.model_dump(mode="json"),
                        locale=submission.locale,
                    )
                    feedback = FeedbackOutcome(status="completed", content=content)
                    _observe(observer, execution_id, operation)
                except Exception as exc:  # pylint: disable=broad-exception-caught
                    logger.exception("Feedback failed (execution_id=%s)", execution_id)
                    feedback_error = OutcomeError(
                        code="FEEDBACK_ERROR", message="Feedback could not be generated.",
                        category=exc.category if isinstance(exc, EvaluationError) else "internal",
                        retryable=exc.retryable if isinstance(exc, EvaluationError) else False,
                        correlation_id=execution_id,
                    )
                    feedback = FeedbackOutcome(status="failed", error=feedback_error)
                    _observe(observer, execution_id, operation, feedback_error)
        except DefinitionValidationError as exc:
            error = OutcomeError(code=exc.errors()[0]["code"],
                                 message="The submission language is not valid for this definition.",
                                 category="submission", retryable=False, correlation_id=execution_id)
        except EvaluationError as exc:
            logger.exception("Required evaluation failed (execution_id=%s)", execution_id)
            error = _outcome_error(exc, execution_id)
        except Exception:  # pylint: disable=broad-exception-caught
            logger.exception("Required evaluation failed (execution_id=%s)", execution_id)
            error = OutcomeError(code="EXECUTION_ERROR", message="The grading execution could not complete.",
                                 category="internal", retryable=False, correlation_id=execution_id)
        finally:
            if error is not None:
                _observe(observer, execution_id, operation, error)
            if session is not None:
                try:
                    session.close()
                    _observe(observer, execution_id, "close_session")
                except Exception:  # pylint: disable=broad-exception-caught
                    logger.exception("Execution session cleanup failed (execution_id=%s)", execution_id)
                    cleanup_error = OutcomeError(code="CLEANUP_ERROR", message="The execution session could not be closed.",
                                                 category="capability", retryable=False, correlation_id=execution_id)
                    _observe(observer, execution_id, "close_session", cleanup_error)

        # Finalization consumes explicit values only, after resource cleanup.
        language = getattr(submission.language, "value", submission.language)
        common = {
            "schema_version": "1.0", "execution_id": execution_id,
            "language": language if language in ("python", "java", "c", "cpp", "node") else None,
            "provenance": self.definition_provenance, "started_at": started_at,
            "finished_at": max(started_at, datetime.now(timezone.utc)),
            "duration_ms": max(0, int((time.monotonic() - started) * 1000)),
        }
        outcome = (FailedOutcome(**common, status="failed", error=error) if error is not None
                   else CompletedOutcome(**common, status="completed", score=tree.score, tree=tree, feedback=feedback))
        return PipelineExecution(outcome)


def build_pipeline(*, definition, locale="en", provenance=None, templates=None, capabilities=None) -> AutograderPipeline:  # pylint: disable=unused-argument
    """Compile without opening resources; retain trusted template instances.

    locale remains accepted for facade compatibility; submission.locale
    selects the language of reports as before.
    """
    compiled = compile_definition(definition, templates=templates)
    provenance = provenance or DefinitionProvenance(definition_hash=compiled.definition_hash)
    if provenance.definition_hash != compiled.definition_hash:
        raise ValueError("Provenance hash must identify the compiled definition")
    return AutograderPipeline(compiled, provenance, capabilities or HostCapabilities())
