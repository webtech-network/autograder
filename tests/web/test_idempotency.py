"""INT-04: caller-keyed acceptance and attestation are safe to replay.

SQLite tests cover the HTTP contract; PostgreSQL tests (TEST_POSTGRES_URL) cover
concurrent duplicates with production unique-constraint semantics.
"""
import asyncio
from copy import deepcopy
import uuid

from httpx import ASGITransport, AsyncClient
import pytest
from sqlalchemy import func, select

from autograder.models.capabilities import HostCapabilities
from tests.web.test_contracts_v1 import definition, external
from tests.web.test_durable_workers import postgres_sessions  # noqa: F401  (fixture)
from web.core.config import Settings
from web.database.models.operation_receipt import OperationReceipt
from web.database.models.submission import Submission
from web.main import create_app
from web.service import submission_operations
from web.service.submission_operations import Idempotency, OperationError, accept_submission, ingest_attested_outcome
from web.schemas import ExternalResultCreate, SubmissionCreate

TOKEN = "int04-integration-token"
PRODUCERS = {"actions": "int04-actions-token", "other": "int04-other-token"}


def bearer(token):
    return {"Authorization": f"Bearer {token}"}


def keyed(key, token=TOKEN):
    return {**bearer(token), "Idempotency-Key": key}


def _app(sessions, tmp_path, evaluator=None):
    app = create_app(Settings(INTEGRATION_TOKEN=TOKEN, ATTESTATION_TOKENS=PRODUCERS,
                              RECEIPT_DIR=str(tmp_path / "receipts"), POLL_SECONDS=0.01),
                     session_factory=sessions, capabilities=HostCapabilities(),
                     evaluator=evaluator, start_workers=False)
    app.state.host.ready = True
    return app


@pytest.fixture
async def app(session_factory, tmp_path):
    application = _app(session_factory, tmp_path)
    yield application
    await application.state.host.close()


@pytest.fixture
async def client(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http:
        yield http


async def create_config(client, alias=None):
    alias = alias or f"assignment-{uuid.uuid4().hex[:8]}"
    response = await client.post("/api/v1/configs", headers=bearer(TOKEN),
                                 json={"external_assignment_id": alias, "definition": definition()})
    assert response.status_code == 200, response.text
    return response.json()


def submission(config, **overrides):
    return {"external_assignment_id": config["external_assignment_id"], "external_user_id": "alice",
            "username": "Alice", "files": [{"filename": "main.py", "content": "print('Hello')"}]} | overrides


async def count(sessions, model):
    async with sessions() as session:
        return await session.scalar(select(func.count()).select_from(model))


# --- acceptance --------------------------------------------------------------------------


async def test_repeated_acceptance_returns_the_original_receipt(client, session_factory):
    config = await create_config(client)
    first = await client.post("/api/v1/submissions", json=submission(config), headers=keyed("prisma-op-1"))
    second = await client.post("/api/v1/submissions", json=submission(config), headers=keyed("prisma-op-1"))
    assert first.status_code == second.status_code == 202
    assert first.json()["id"] == second.json()["id"]
    assert first.headers["Location"] == second.headers["Location"]
    assert first.headers["Idempotent-Replayed"] == "false"
    assert second.headers["Idempotent-Replayed"] == "true"
    assert await count(session_factory, Submission) == 1
    assert await count(session_factory, OperationReceipt) == 1


async def test_key_reuse_with_different_request_is_a_typed_conflict(client, session_factory):
    config = await create_config(client)
    assert (await client.post("/api/v1/submissions", json=submission(config), headers=keyed("k"))).status_code == 202
    changed = submission(config, files=[{"filename": "main.py", "content": "print('Changed')"}])
    response = await client.post("/api/v1/submissions", json=changed, headers=keyed("k"))
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "IDEMPOTENCY_KEY_REUSED"
    assert await count(session_factory, Submission) == 1


async def test_equivalent_json_encodings_are_the_same_request(client):
    config = await create_config(client)
    body = submission(config)
    first = await client.post("/api/v1/submissions", json=body, headers=keyed("enc"))
    reordered = dict(reversed(list(body.items())))
    second = await client.post("/api/v1/submissions", json=reordered | {"language": "PYTHON"}, headers=keyed("enc"))
    third = await client.post("/api/v1/submissions", json=reordered | {"language": "python"}, headers=keyed("enc"))
    # Key order is irrelevant; a field the first request omitted is a different request,
    # even when it normalizes to the inferred value.
    assert second.status_code == 409
    assert third.status_code == 409
    assert (await client.post("/api/v1/submissions", json=reordered, headers=keyed("enc"))).json()["id"] == \
        first.json()["id"]


async def test_unkeyed_acceptance_keeps_creating_new_work(client, session_factory):
    config = await create_config(client)
    for _ in range(2):
        response = await client.post("/api/v1/submissions", json=submission(config), headers=bearer(TOKEN))
        assert response.headers["Idempotent-Replayed"] == "false"
    assert await count(session_factory, Submission) == 2
    assert await count(session_factory, OperationReceipt) == 0


async def test_replay_after_revision_change_and_deactivation_returns_original_binding(client, session_factory):
    config = await create_config(client)
    first = (await client.post("/api/v1/submissions", json=submission(config), headers=keyed("rev"))).json()
    changed = deepcopy(config["definition"])
    changed["criteria"]["base"]["tests"][0]["name"] = "Renamed"
    patched = await client.patch(f"/api/v1/configs/{config['id']}", json={"definition": changed},
                                 headers={**bearer(TOKEN), "If-Match": '"1"'})
    assert patched.json()["version"] == 2
    replay = await client.post("/api/v1/submissions", json=submission(config), headers=keyed("rev"))
    assert replay.status_code == 202 and replay.json()["id"] == first["id"]
    assert replay.json()["provenance"] == first["provenance"]
    assert replay.json()["provenance"]["revision"] == 1
    await client.patch(f"/api/v1/configs/{config['id']}", json={"is_active": False},
                       headers={**bearer(TOKEN), "If-Match": '"2"'})
    replay = await client.post("/api/v1/submissions", json=submission(config), headers=keyed("rev"))
    assert replay.status_code == 202 and replay.json()["id"] == first["id"]
    # A new key is new work and is gated by today's activation state.
    fresh = await client.post("/api/v1/submissions", json=submission(config), headers=keyed("rev-2"))
    assert fresh.status_code == 409
    assert await count(session_factory, Submission) == 1


@pytest.mark.parametrize("key", ["", "has space", "x" * 256, "tab\tkey", "del\x7f"])
async def test_invalid_keys_are_rejected_before_any_work(client, session_factory, key):
    config = await create_config(client)
    response = await client.post("/api/v1/submissions", json=submission(config),
                                 headers={**bearer(TOKEN), "Idempotency-Key": key})
    assert response.status_code == 422
    assert await count(session_factory, Submission) == 0


async def test_replay_does_not_grade_again(session_factory, tmp_path):
    graded = []

    async def evaluate(request, capabilities):
        from web.service.grading_service import failed_outcome
        graded.append(request.submission_id)
        return failed_outcome(request)

    app = _app(session_factory, tmp_path, evaluator=evaluate)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        config = await create_config(client)
        first = await client.post("/api/v1/submissions", json=submission(config), headers=keyed("grade-once"))
        await app.state.host.worker.run_once()
        assert graded == [first.json()["id"]]
        for _ in range(3):
            replay = await client.post("/api/v1/submissions", json=submission(config), headers=keyed("grade-once"))
            assert replay.json()["status"] == "failed"  # the finished original, not new work
        await app.state.host.worker.run_once()
        assert graded == [first.json()["id"]]
    await app.state.host.close()


# --- attestation -------------------------------------------------------------------------


async def test_repeated_attestation_creates_one_result(client, session_factory):
    config = await create_config(client)
    payload = external(config, score=80)
    first = await client.post("/api/v1/submissions/external-results", json=payload,
                              headers=keyed("run-1-attempt-1", PRODUCERS["actions"]))
    second = await client.post("/api/v1/submissions/external-results", json=payload,
                               headers=keyed("run-1-attempt-1", PRODUCERS["actions"]))
    assert first.status_code == second.status_code == 200
    assert first.json() == second.json()
    assert second.headers["Idempotent-Replayed"] == "true"
    assert await count(session_factory, Submission) == 1


async def test_changed_attestation_under_same_key_conflicts(client):
    config = await create_config(client)
    headers = keyed("attempt", PRODUCERS["actions"])
    assert (await client.post("/api/v1/submissions/external-results", json=external(config, score=80),
                              headers=headers)).status_code == 200
    response = await client.post("/api/v1/submissions/external-results", json=external(config, score=100),
                                 headers=headers)
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "IDEMPOTENCY_KEY_REUSED"


async def test_producers_cannot_collide_or_read_each_others_receipts(client, session_factory):
    config = await create_config(client)
    mine = await client.post("/api/v1/submissions/external-results", json=external(config, score=10),
                             headers=keyed("shared-key", PRODUCERS["actions"]))
    theirs = await client.post("/api/v1/submissions/external-results", json=external(config, score=90),
                               headers=keyed("shared-key", PRODUCERS["other"]))
    assert mine.status_code == theirs.status_code == 200
    assert mine.json()["submission_id"] != theirs.json()["submission_id"]
    # Replaying my payload under the shared key never yields the other producer's receipt.
    replay = await client.post("/api/v1/submissions/external-results", json=external(config, score=90),
                               headers=keyed("shared-key", PRODUCERS["actions"]))
    assert replay.status_code == 409
    assert "90" not in str(replay.json()["detail"])
    assert await count(session_factory, Submission) == 2


async def test_acceptance_and_attestation_keys_are_separate_operations(client, session_factory):
    config = await create_config(client)
    accepted = await client.post("/api/v1/submissions", json=submission(config), headers=keyed("same"))
    attested = await client.post("/api/v1/submissions/external-results", json=external(config, score=1),
                                 headers=keyed("same"))
    assert accepted.status_code == 202 and attested.status_code == 200
    assert accepted.json()["id"] != attested.json()["submission_id"]


async def test_attestation_replay_after_revision_change(client):
    config = await create_config(client)
    payload = external(config, score=70)
    first = (await client.post("/api/v1/submissions/external-results", json=payload,
                               headers=keyed("old-rev", PRODUCERS["actions"]))).json()
    changed = deepcopy(config["definition"])
    changed["criteria"]["base"]["tests"][0]["name"] = "Renamed"
    await client.patch(f"/api/v1/configs/{config['id']}", json={"definition": changed},
                       headers={**bearer(TOKEN), "If-Match": '"1"'})
    replay = await client.post("/api/v1/submissions/external-results", json=payload,
                               headers=keyed("old-rev", PRODUCERS["actions"]))
    assert replay.status_code == 200 and replay.json() == first


async def test_failed_transaction_rolls_back_resource_and_replay_state(session_factory, monkeypatch, client):
    config = await create_config(client)
    payload = ExternalResultCreate.model_validate(external(config, score=50))
    original = submission_operations.persist_outcome

    async def interrupted(*args, **kwargs):
        await original(*args, **kwargs)
        raise RuntimeError("connection lost before commit")

    monkeypatch.setattr(submission_operations, "persist_outcome", interrupted)
    async with session_factory() as session:
        with pytest.raises(RuntimeError):
            await ingest_attested_outcome(session, payload, Idempotency("attestation:actions", "lost"))
    assert await count(session_factory, Submission) == 0
    assert await count(session_factory, OperationReceipt) == 0
    monkeypatch.setattr(submission_operations, "persist_outcome", original)
    async with session_factory() as session:
        receipt, replayed = await ingest_attested_outcome(session, payload, Idempotency("attestation:actions", "lost"))
    assert replayed is False and receipt["final_score"] == 50


async def test_commit_then_lost_response_is_recovered_by_retry(session_factory, client):
    """The first request commits but the caller never sees the response."""
    config = await create_config(client)
    body = external(config, score=60)
    async with session_factory() as session:
        committed, _ = await ingest_attested_outcome(session, ExternalResultCreate.model_validate(body),
                                                     Idempotency("attestation:actions", "lost-ack"))
    retry = await client.post("/api/v1/submissions/external-results", json=body,
                              headers=keyed("lost-ack", PRODUCERS["actions"]))
    assert retry.status_code == 200
    assert retry.json()["submission_id"] == committed["submission_id"]
    assert retry.headers["Idempotent-Replayed"] == "true"


async def test_conflict_detail_is_safe(session_factory, client):
    config = await create_config(client)
    async with session_factory() as session:
        await accept_submission(session, SubmissionCreate.model_validate(submission(config)), Idempotency("integration", "x"))
    async with session_factory() as session:
        with pytest.raises(OperationError) as error:
            await accept_submission(session, SubmissionCreate.model_validate(
                submission(config, external_user_id="mallory")), Idempotency("integration", "x"))
    assert error.value.status_code == 409
    assert "alice" not in str(error.value.detail)


# --- PostgreSQL concurrency --------------------------------------------------------------


@pytest.fixture
async def pg_client(postgres_sessions, tmp_path):  # noqa: F811
    application = _app(postgres_sessions, tmp_path)
    async with AsyncClient(transport=ASGITransport(app=application), base_url="http://test") as http:
        yield http
    await application.state.host.close()


async def test_concurrent_duplicate_acceptance_creates_one_submission(pg_client, postgres_sessions):  # noqa: F811
    config = await create_config(pg_client)
    responses = await asyncio.gather(*(
        pg_client.post("/api/v1/submissions", json=submission(config), headers=keyed("race"))
        for _ in range(12)))
    assert {response.status_code for response in responses} == {202}
    assert len({response.json()["id"] for response in responses}) == 1
    assert sorted(response.headers["Idempotent-Replayed"] for response in responses).count("false") == 1
    assert await count(postgres_sessions, Submission) == 1
    assert await count(postgres_sessions, OperationReceipt) == 1


async def test_concurrent_duplicate_attestation_creates_one_result(pg_client, postgres_sessions):  # noqa: F811
    config = await create_config(pg_client)
    payload = external(config, score=40)
    responses = await asyncio.gather(*(
        pg_client.post("/api/v1/submissions/external-results", json=payload,
                       headers=keyed("race", PRODUCERS["actions"]))
        for _ in range(12)))
    assert {response.status_code for response in responses} == {200}
    assert len({response.json()["submission_id"] for response in responses}) == 1
    assert await count(postgres_sessions, Submission) == 1


async def test_concurrent_differing_requests_one_wins_others_conflict(pg_client, postgres_sessions):  # noqa: F811
    config = await create_config(pg_client)
    responses = await asyncio.gather(*(
        pg_client.post("/api/v1/submissions/external-results", json=external(config, score=score),
                       headers=keyed("contended", PRODUCERS["actions"]))
        for score in range(0, 100, 10)))
    statuses = sorted(response.status_code for response in responses)
    assert statuses.count(200) == 1 and statuses.count(409) == 9
    assert await count(postgres_sessions, Submission) == 1


async def test_postgres_rollback_leaves_no_receipt(pg_client, postgres_sessions, monkeypatch):  # noqa: F811
    config = await create_config(pg_client)
    original = submission_operations.persist_outcome

    async def interrupted(*args, **kwargs):
        await original(*args, **kwargs)
        raise RuntimeError("interrupted")

    monkeypatch.setattr(submission_operations, "persist_outcome", interrupted)
    with pytest.raises(RuntimeError):
        await pg_client.post("/api/v1/submissions/external-results", json=external(config, score=5),
                             headers=keyed("pg-rollback", PRODUCERS["actions"]))
    assert await count(postgres_sessions, Submission) == 0
    assert await count(postgres_sessions, OperationReceipt) == 0
