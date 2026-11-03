"""Concrete web operations own transactions; routes translate HTTP concerns."""
from dataclasses import dataclass
from datetime import timezone
import hashlib
import json

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from autograder.models.contracts.definition import compile_definition, select_language, DefinitionValidationError
from autograder.services.weights import normalized_sibling_weights
from web.database.models.submission import SubmissionStatus
from web.database.models.operation_receipt import OperationReceipt
from web.repositories import GradingConfigRepository, SubmissionRepository, ResultRepository
from web.service.outcome_delivery import persist_outcome


ACCEPT_OPERATION = "submission.accept"
ATTEST_OPERATION = "outcome.attest"


@dataclass(frozen=True)
class Idempotency:
    """A caller-chosen key, namespaced by the authenticated principal (INT-04)."""

    principal: str
    key: str


class OperationError(ValueError):
    def __init__(self, status_code, detail):
        self.status_code = status_code
        self.detail = detail
        super().__init__(str(detail))


def _utc(value):
    return (
        value.replace(tzinfo=timezone.utc)
        if value is not None and value.tzinfo is None
        else value
    )


def project_submission(row, *, details=False):
    result = row.result
    outcome = result.outcome if result else None
    error = outcome.get("error") if outcome else None
    if not outcome and row.status == SubmissionStatus.FAILED:
        error = {
            "code": "LEGACY_UNVERIFIED" if result else "RECOVERY_INPUT_UNAVAILABLE",
            "message": ("This historical execution predates the verified outcome contract." if result
                        else "This unfinished historical submission lacks complete replayable input."),
            "category": "internal",
            "retryable": False,
            "correlation_id": f"legacy-submission-{row.id}",
        }
    # Legacy failures carried a numeric zero. It is never an authoritative grade.
    score = (
        outcome["score"]
        if outcome
        else (
            result.final_score
            if result and row.status == SubmissionStatus.COMPLETED
            else None
        )
    )
    data = {
        "id": row.id,
        "grading_config_id": row.grading_config_id,
        "external_user_id": row.external_user_id,
        "username": row.username,
        "language": row.language,
        "status": row.status,
        "submitted_at": _utc(row.submitted_at),
        "graded_at": _utc(row.graded_at),
        "final_score": score,
        "execution_time_ms": (
            outcome["duration_ms"]
            if outcome
            else (result.execution_time_ms if result else None)
        ),
        "provenance": (
            outcome["provenance"]
            if outcome
            else (
                {
                    "schema_version": "1.0",
                    "definition_hash": row.definition_hash,
                    "reference": str(row.grading_config_id),
                    "revision": row.configuration_version,
                }
                if row.definition_hash
                else None
            )
        ),
        "provenance_status": (
            "bound_snapshot" if row.definition_hash else "unverified_legacy"
        ),
        "error": error,
        "feedback_status": outcome["feedback"]["status"] if outcome else None,
        "comparison_status": outcome["comparison"]["status"] if outcome else None,
    }
    if details:
        data.update(
            submission_files={
                name: ({"filename": name, **value} if isinstance(value, dict)
                       else {"filename": name, "content": str(value)})
                for name, value in row.submission_files.items()
            },
            submission_metadata=row.submission_metadata,
            locale=row.locale,
            evaluation_scope=row.evaluation_scope,
            definition_snapshot=row.definition_snapshot,
            outcome=outcome,
            diagnostics=result.diagnostics if result else None,
        )
    return data


def _compile(value):
    try:
        return compile_definition(value)
    except DefinitionValidationError as exc:
        raise OperationError(422, detail=exc.errors()) from exc


def _check_attested_tree(outcome, compiled):
    """Attestation may not change criterion placement or scoring ratios."""
    from math import isclose

    if outcome["status"] != "completed":
        return

    def mismatch():
        raise OperationError(
            422,
            "Result tree structure, identities or scoring weights do not match its definition snapshot",
        )

    def holder(expected, actual):
        if actual["name"] != expected.name:
            mismatch()
        for key in ("subjects", "tests"):
            children = getattr(expected, key)
            actual_children = actual.get(key) or []
            if len(children) != len(actual_children):
                mismatch()
            factor = 100.0
            if expected.subjects and expected.tests:
                factor = (
                    expected.subjects_weight
                    if key == "subjects"
                    else 100.0 - expected.subjects_weight
                )
            weights = normalized_sibling_weights([child.weight for child in children], factor / 100.0)
            for child, result, normalized_weight in zip(children, actual_children, weights):
                if not isclose(result["weight"], normalized_weight, abs_tol=0.00001):
                    mismatch()
                if key == "tests":
                    if (
                        result["id"] != child.criterion_id
                        or result["evaluator"] != child.test_function.name
                        or result["name"] != child.name
                        or result.get("file_target") != child.file_target
                    ):
                        mismatch()
                else:
                    holder(child, result)

    tree = outcome["tree"]
    for category in ("base", "bonus", "penalty"):
        expected = getattr(compiled.criteria_tree, category)
        actual = tree.get(category)
        if (expected is None) != (actual is None):
            mismatch()
        if expected:
            if not isclose(expected.weight, actual["weight"], abs_tol=0.00001):
                mismatch()
            holder(expected, actual)


def request_fingerprint(request) -> str:
    """SHA-256 over the validated request's canonical JSON."""
    canonical = json.dumps(request.model_dump(mode="json"), sort_keys=True,
                           separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


async def _replayed_submission(session, operation, idempotency, fingerprint):
    receipt = await session.scalar(select(OperationReceipt).where(
        OperationReceipt.principal == idempotency.principal,
        OperationReceipt.operation == operation,
        OperationReceipt.idempotency_key == idempotency.key,
    ))
    if receipt is None:
        return None
    if receipt.fingerprint != fingerprint:
        raise OperationError(409, {
            "code": "IDEMPOTENCY_KEY_REUSED",
            "message": "This Idempotency-Key was already used with a different request",
        })
    return receipt.submission_id


async def _run_keyed(session, operation, idempotency, request, create):
    """Create once per (principal, operation, key); return (submission_id, replayed).

    The resource and its receipt commit in one transaction. A replay never runs
    `create`, so it never reselects a definition, revalidates against today's
    configuration, or schedules grading again.
    """
    fingerprint = request_fingerprint(request) if idempotency else None
    try:
        if idempotency is not None:
            existing = await _replayed_submission(session, operation, idempotency, fingerprint)
            if existing is not None:
                return existing, True
        row = await create()
        if idempotency is not None:
            session.add(OperationReceipt(principal=idempotency.principal, operation=operation,
                                         idempotency_key=idempotency.key, fingerprint=fingerprint,
                                         submission_id=row.id))
            await session.flush()
        await session.commit()
        return row.id, False
    except IntegrityError:
        await session.rollback()
        if idempotency is None:
            raise
        # A concurrent equal request committed first: converge on its resource.
        existing = await _replayed_submission(session, operation, idempotency, fingerprint)
        if existing is None:
            raise
        return existing, True
    except Exception:
        await session.rollback()
        raise


async def accept_submission(session, submission, idempotency: Idempotency | None = None):
    """Accept work once; return (submission row, replayed)."""
    submission_id, replayed = await _run_keyed(
        session, ACCEPT_OPERATION, idempotency, submission,
        lambda: _accept_submission(session, submission))
    return await SubmissionRepository(session).get_by_id_with_result(submission_id), replayed


async def ingest_attested_outcome(session, payload, idempotency: Idempotency | None = None):
    """Store one attestation; return (receipt, replayed)."""
    submission_id, replayed = await _run_keyed(
        session, ATTEST_OPERATION, idempotency, payload,
        lambda: _ingest_attested_outcome(session, payload))
    row = await SubmissionRepository(session).get_by_id_with_result(submission_id, include_files=False)
    return attestation_receipt(row), replayed


def attestation_receipt(row):
    outcome = row.result.outcome
    return {
        "submission_id": row.id,
        "grading_config_id": row.grading_config_id,
        "status": row.status,
        "final_score": outcome["score"],
        "language": row.language,
        "provenance": outcome["provenance"],
        "graded_at": _utc(row.graded_at),
        "execution_time_ms": outcome["duration_ms"],
    }


async def query_history(session, **filters):
    return [project_submission(row) for row in await SubmissionRepository(session).history(**filters)]


async def query_submission(session, submission_id, *, details=False):
    row = await SubmissionRepository(session).get_by_id_with_result(submission_id, include_files=details)
    if row is None:
        raise OperationError(404, "Submission not found")
    return project_submission(row, details=details)


async def _accept_submission(session, submission):
    config = await GradingConfigRepository(session).get_by_external_id(
        submission.external_assignment_id
    )
    if config is None:
        raise OperationError(404, "Grading configuration not found")
    if not config.is_active or config.definition is None:
        raise OperationError(
            409, "Grading configuration is inactive or requires migration"
        )
    compiled = _compile(config.definition)
    try:
        language = select_language(compiled.definition, submission.language)
    except DefinitionValidationError as exc:
        raise OperationError(422, detail=exc.errors()) from exc
    except ValueError as exc:
        raise OperationError(
            422,
            detail=[
                {"code": "INVALID_LANGUAGE", "path": ["language"], "message": str(exc)}
            ],
        ) from exc
    files = {file.filename: file.model_dump() for file in submission.files}
    repo = SubmissionRepository(session)
    row = await repo.create(
        grading_config_id=config.id,
        external_user_id=submission.external_user_id,
        username=submission.username,
        submission_files=files,
        language=language.value,
        submission_metadata=submission.metadata,
        definition_snapshot=compiled.definition.model_dump(mode="json"),
        definition_hash=compiled.definition_hash,
        configuration_version=config.version,
        locale=submission.locale or "en",
        evaluation_scope=submission.evaluation_scope.model_dump() if submission.evaluation_scope is not None else None,
    )
    return row


async def _ingest_attested_outcome(session, payload):
    config = await GradingConfigRepository(session).get_by_id(payload.grading_config_id)
    if config is None:
        raise OperationError(404, "Grading configuration not found")
    compiled = _compile(payload.definition_snapshot)
    outcome = payload.outcome.model_dump(mode="json")
    provenance = outcome["provenance"]
    if provenance["definition_hash"] != compiled.definition_hash or provenance.get(
        "reference"
    ) != str(config.id):
        raise OperationError(
            422, "Outcome provenance does not match its definition snapshot/resource"
        )
    revision = provenance.get("revision")
    if revision is None or revision > config.version:
        raise OperationError(
            422, "Outcome must attest a known positive configuration revision"
        )
    if (
        revision == config.version
        and compiled.definition_hash != config.definition_hash
    ):
        raise OperationError(
            422, "Current revision attestation must match the stored definition hash"
        )
    if (
        outcome["language"] != payload.language
        or payload.language not in compiled.definition.languages
    ):
        raise OperationError(
            422, "Outcome language does not match its definition snapshot"
        )
    _check_attested_tree(outcome, compiled)
    repo = SubmissionRepository(session)
    row = await repo.create(
        grading_config_id=config.id,
        external_user_id=payload.external_user_id,
        username=payload.username,
        submission_files={},
        language=payload.language,
        submission_metadata=payload.submission_metadata,
        definition_snapshot=compiled.definition.model_dump(mode="json"),
        definition_hash=compiled.definition_hash,
        configuration_version=revision,
    )
    await persist_outcome(ResultRepository(session), repo, row.id, outcome)
    return row
