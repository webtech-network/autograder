"""The API's structured logs: route templates, request ids, worker correlation (#487)."""
import asyncio
import io
import json
import logging

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from autograder.models.capabilities import HostCapabilities
from sandbox_manager.structured_logging import REQUEST_ID_HEADER, _ServiceHandler, get_request_id
from tests.web.test_contracts_v1 import definition
from web.core.config import Settings
from web.database.models.grading_attempt import GradingAttempt
from web.service.grading_service import evaluate

TOKEN = "request-logging-token"


@pytest.fixture
async def logged(session_factory, tmp_path):
    """A JSON-logging API, a client and a reader of the JSON lines it wrote."""
    from web.main import create_app
    seen = []

    async def observed(request, capabilities=None):
        seen.append(get_request_id())
        return await evaluate(request, capabilities)

    app = create_app(Settings(RECEIPT_DIR=str(tmp_path / "receipts"), INTEGRATION_TOKEN=TOKEN, JSON_LOGS=True,
                              APP_ENV="staging"),
                     session_factory=session_factory, capabilities=HostCapabilities(), evaluator=observed,
                     start_workers=False)
    app.state.host.ready = True
    root = logging.getLogger()
    stream = io.StringIO()
    for handler in root.handlers:
        if isinstance(handler, _ServiceHandler):
            handler.setStream(stream)

    def lines():
        out = stream.getvalue()
        return out, [json.loads(line) for line in out.splitlines()]

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test",
                           headers={"Authorization": f"Bearer {TOKEN}"}) as client:
        yield app, client, lines, seen
    await app.state.host.close()
    for handler in [h for h in root.handlers if isinstance(h, _ServiceHandler)]:
        root.removeHandler(handler)


def request_lines(records):
    return [r for r in records if r["message"] in ("http_request_completed", "http_request_failed")]


@pytest.mark.asyncio
async def test_request_lines_log_route_templates_never_student_ids_or_tokens(logged):
    _, client, lines, _ = logged
    response = await client.get("/api/v1/submissions/user/student-77?limit=5",
                                headers={REQUEST_ID_HEADER: "prisma-req-1"})
    assert response.status_code == 200
    assert response.headers[REQUEST_ID_HEADER] == "prisma-req-1"
    out, records = lines()
    assert "student-77" not in out and TOKEN not in out and "limit=5" not in out
    [line] = request_lines(records)
    assert line["path"] == "/api/v1/submissions/user/{external_user_id}"
    assert line["method"] == "GET" and line["status"] == 200 and line["request_id"] == "prisma-req-1"
    assert line["service"] == "autograder-api" and line["env"] == "staging"


@pytest.mark.asyncio
async def test_a_malformed_request_id_is_replaced(logged):
    _, client, lines, _ = logged
    response = await client.get("/api/v1/health", headers={REQUEST_ID_HEADER: "x" * 129})
    fresh = response.headers[REQUEST_ID_HEADER]
    assert fresh != "x" * 129 and len(fresh) == 32
    _, records = lines()
    assert [line["request_id"] for line in request_lines(records)] == [fresh]


@pytest.mark.asyncio
async def test_the_worker_grades_under_its_attempt_id(logged, session_factory):
    app, client, _, seen = logged
    assert (await client.post("/api/v1/configs", json={"external_assignment_id": "logs",
                                                       "definition": definition()})).status_code == 200
    accepted = await client.post("/api/v1/submissions", json={
        "external_assignment_id": "logs", "external_user_id": "student", "username": "Student",
        "files": [{"filename": "main.py", "content": "print('ok')\n"}]})
    assert accepted.status_code == 202, accepted.text
    # Outside any HTTP request, as the worker loop runs.
    assert await asyncio.create_task(app.state.host.worker.run_once()) is True
    async with session_factory() as session:
        attempt_id = await session.scalar(select(GradingAttempt.id))
    assert seen == [str(attempt_id)]
    assert get_request_id() is None
