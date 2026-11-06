"""AI assessment over real HTTP calls and the durable worker (ARC-07).

The host injects a fake provider through HostCapabilities; configurations are
created, submissions accepted and graded by the worker, and outcomes read back
through authenticated details.
"""
import pytest
from httpx import ASGITransport, AsyncClient

from autograder.models.capabilities import HostCapabilities
from autograder.models.execution import ProviderAssessment
from web.core.config import Settings
from tests.grading import FakeProvider
from tests.web.worker_support import drain

HEADERS = {"Authorization": "Bearer ai-token"}

DEFINITION = {
    "schema_version": "1.0", "templates": ["static_analysis"], "languages": ["python"],
    "criteria": {"base": {"weight": 100, "subjects": [
        {"subject_name": "Algorithms", "weight": 3, "tests": [
            {"id": "merge", "type": "ai_sorting_algorithm", "name": "Algorithm / review",
             "parameters": {"algorithm_name": "merge sort"}, "weight": 1},
            {"id": "quick", "type": "ai_sorting_algorithm", "name": "Algorithm / review",
             "parameters": {"algorithm_name": "quick sort"}, "weight": 3},
        ]},
        {"subject_name": "Hygiene", "weight": 1, "tests": [
            {"id": "imports", "type": "forbidden_import", "name": "Imports",
             "parameters": {"forbidden_imports": ["os"]}},
        ]},
    ]}},
}


@pytest.fixture(autouse=True)
def integration_token(monkeypatch):
    monkeypatch.setenv("AUTOGRADER_INTEGRATION_TOKEN", "ai-token")


@pytest.fixture
def provider():
    scores = {"merge": 100.0, "quick": 20.0}
    return FakeProvider(lambda requests: [
        ProviderAssessment(request.criterion_id, scores[request.criterion_id], f"report {request.criterion_id}")
        for request in requests])


@pytest.fixture
async def ai_client(session_factory, tmp_path, provider):
    from web.main import create_app  # pylint: disable=import-outside-toplevel
    app = create_app(Settings(RECEIPT_DIR=str(tmp_path / "receipts"), INTEGRATION_TOKEN="ai-token"), session_factory=session_factory,
                     capabilities=HostCapabilities(ai=provider), start_workers=False)
    app.state.host.ready = True
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", headers=HEADERS) as client:
        yield app, client
    await app.state.host.close()


async def submit(app, client, assignment, files):
    created = await client.post("/api/v1/configs", json={"external_assignment_id": assignment, "definition": DEFINITION})
    assert created.status_code == 200, created.text
    submitted = await client.post("/api/v1/submissions", json={
        "external_assignment_id": assignment, "external_user_id": "student", "username": "Student",
        "files": [{"filename": name, "content": content} for name, content in files.items()]})
    assert submitted.status_code == 202, submitted.text
    await drain(app.state.host.worker, app.state.host.worker.sessions)
    polled = (await client.get(submitted.headers["Location"])).json()
    details = await client.get(f'/api/v1/submissions/{polled["id"]}/details', headers=HEADERS)
    assert details.status_code == 200, details.text
    return polled, details.json()["outcome"]


@pytest.mark.asyncio
async def test_mixed_ai_and_static_rubric_is_graded_with_one_provider_call(ai_client, provider):
    app, client = ai_client
    files = {"main.py": "def sort(items):\n    return items\n", "README.md": "docs"}
    polled, outcome = await submit(app, client, "ai-mixed", files)
    assert polled["status"] == "completed" and outcome["error"] is None
    [algorithms, hygiene] = outcome["tree"]["base"]["subjects"]
    assert [(t["id"], t["name"], t["evaluator"], t["score"], t["report"]) for t in algorithms["tests"]] == [
        ("merge", "Algorithm / review", "ai_sorting_algorithm", 100, "report merge"),
        ("quick", "Algorithm / review", "ai_sorting_algorithm", 20, "report quick"),
    ]
    assert hygiene["tests"][0]["score"] == 100
    # Algorithms: (100*1 + 20*3)/4 = 40, weighted 3:1 with hygiene 100 -> 55.
    assert algorithms["score"] == 40 and polled["final_score"] == 55
    [(requests, context, locale)] = provider.calls
    assert [request.criterion_id for request in requests] == ["merge", "quick"]
    assert "merge sort" in requests[0].prompt and "quick sort" in requests[1].prompt
    assert context == files and locale == "en"


@pytest.mark.asyncio
@pytest.mark.parametrize("answer,code", [
    (lambda requests: [ProviderAssessment("merge", 100)], "MISSING_EVALUATOR_RESULT"),
    (lambda requests: [ProviderAssessment(r.criterion_id, 100) for r in (*requests, requests[0])],
     "INVALID_EVALUATOR_RESULT"),
    (lambda requests: [ProviderAssessment(r.criterion_id, 100) for r in requests] + [ProviderAssessment("x", 1)],
     "INVALID_EVALUATOR_RESULT"),
    (lambda requests: [ProviderAssessment(r.criterion_id, 150) for r in requests], "INVALID_EVALUATOR_RESULT"),
])
async def test_invalid_provider_output_fails_over_http_without_a_grade(ai_client, provider, answer, code):
    app, client = ai_client
    provider.answer = answer
    polled, outcome = await submit(app, client, "ai-invalid", {"main.py": "x = 1"})
    assert polled["status"] == "failed" and polled["final_score"] is None
    assert outcome["tree"] is None and outcome["score"] is None
    assert outcome["error"]["code"] == code and outcome["error"]["category"] == "provider"
    # Invalid model output may differ on the next call: retryable, one provider call per attempt.
    assert outcome["error"]["retryable"] is True
    assert len(provider.calls) == app.state.host.settings.MAX_ATTEMPTS
