"""Input boundaries fail before durable acceptance and preserve supported source."""

from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError

from submission_contract import (
    MAX_FILES, MAX_FILE_BYTES, MAX_TOTAL_FILE_BYTES, MAX_METADATA_BYTES,
    MAX_TOTAL_METADATA_BYTES, MAX_PATH_BYTES, MAX_REQUEST_BYTES,
)
from web.config.body_limit import RequestBodyLimitMiddleware
from web.schemas.submission import SubmissionCreate, SubmissionFileData


@pytest.fixture(autouse=True)
def input_auth(monkeypatch):
    """Configure the token before the application reads its settings."""
    monkeypatch.setenv("AUTOGRADER_INTEGRATION_TOKEN", "input-test-token")


def payload(**updates):
    value = {"external_assignment_id": "assignment", "external_user_id": "student",
             "username": "Student", "files": [{"filename": "main.py", "content": "pass\n"}]}
    value.update(updates)
    return value


@pytest.mark.parametrize("name", [
    "", "/main.py", "../main.py", "src/../main.py", "./main.py", "src//main.py",
    "src/./main.py", "src/", "C:/main.py", "C:main.py", "src\\main.py",
    "//host/main.py", ".", "..", "main\x00.py", "main\n.py", "cafe\u0301.py",
])
def test_noncanonical_paths_are_rejected(name):
    with pytest.raises(ValidationError):
        SubmissionFileData(filename=name, content="pass")


def test_path_and_source_byte_boundaries_and_exact_contents():
    content = "# café\r\npass\r\n"
    assert SubmissionFileData(filename="src/café.py", content=content).content == content
    assert SubmissionFileData(filename="a" * MAX_PATH_BYTES, content="").filename
    with pytest.raises(ValidationError):
        SubmissionFileData(filename="é" * (MAX_PATH_BYTES // 2 + 1), content="")
    content = "é" * (MAX_FILE_BYTES // 2)
    assert SubmissionFileData(filename="main.py", content=content).content == content
    with pytest.raises(ValidationError):
        SubmissionFileData(filename="main.py", content=content + "a")


@pytest.mark.parametrize("content", ["\x00", "\ud800"])
def test_unsupported_binary_or_unicode_rejected(content):
    with pytest.raises(ValidationError):
        SubmissionFileData(filename="main.py", content=content)


def test_file_count_total_bytes_and_empty_submission_boundaries():
    files = [{"filename": f"{i}.py", "content": ""} for i in range(MAX_FILES)]
    assert len(SubmissionCreate(**payload(files=files)).files) == MAX_FILES
    for invalid in ([], files + [{"filename": "extra.py", "content": ""}]):
        with pytest.raises(ValidationError):
            SubmissionCreate(**payload(files=invalid))
    files = [{"filename": f"{i}.py", "content": "a" * MAX_FILE_BYTES}
             for i in range(MAX_TOTAL_FILE_BYTES // MAX_FILE_BYTES)]
    assert SubmissionCreate(**payload(files=files))
    with pytest.raises(ValidationError):
        SubmissionCreate(**payload(files=files + [{"filename": "extra.py", "content": "a"}]))


@pytest.mark.parametrize("names", [["main.py", "main.py"], ["src", "src/main.py"]])
def test_duplicates_and_file_directory_collisions(names):
    with pytest.raises(ValidationError):
        SubmissionCreate(**payload(files=[{"filename": name, "content": ""} for name in names]))


@pytest.mark.parametrize("scope", [[], ["missing.py"], ["main.py", "main.py"], ["./main.py"]])
def test_scope_is_a_nonempty_unique_subset(scope):
    with pytest.raises(ValidationError):
        SubmissionCreate(**payload(evaluation_scope={"scoped_files": scope}))


@pytest.mark.parametrize("lines", [[0], [-1], [3], [1, 1], [True], [1.0], ["1"]])
def test_changed_lines_are_unique_existing_one_based_integers(lines):
    with pytest.raises(ValidationError):
        SubmissionFileData(filename="main.py", content="pass\r\nx=1\r\n", changed_lines=lines)


def test_absent_empty_and_valid_changed_lines_remain_distinct():
    assert SubmissionFileData(filename="main.py", content="").changed_lines is None
    assert SubmissionFileData(filename="main.py", content="", changed_lines=[]).changed_lines == []
    assert SubmissionFileData(filename="main.py", content="a\nb", changed_lines=[2, 1]).changed_lines == [2, 1]
    with pytest.raises(ValidationError):
        SubmissionFileData(filename="main.py", content="", changed_lines=[1])


def test_metadata_limits_use_finite_compact_utf8_json():
    metadata = {"x": "a" * (MAX_METADATA_BYTES - len('{"x":""}'))}
    assert SubmissionCreate(**payload(metadata=metadata)).metadata == metadata
    for value in ({"x": metadata["x"] + "a"}, {"x": float("nan")}, {"x": "\ud800"}):
        with pytest.raises(ValidationError):
            SubmissionCreate(**payload(metadata=value))
    files = [{"filename": f"{i}.py", "content": "", "file_metadata": metadata}
             for i in range(MAX_TOTAL_METADATA_BYTES // MAX_METADATA_BYTES)]
    assert SubmissionCreate(**payload(files=files))
    with pytest.raises(ValidationError):
        SubmissionCreate(**payload(files=files, metadata={"extra": True}))


@pytest.mark.parametrize("field", ["unknown", "encoding", "role"])
def test_unknown_source_fields_are_not_silently_discarded(field):
    file = {"filename": "main.py", "content": "pass", field: "value"}
    with pytest.raises(ValidationError):
        SubmissionCreate(**payload(files=[file]))


@pytest.mark.asyncio
@pytest.mark.parametrize("invalid", [
    payload(files=[]), payload(files=[{"filename": "../main.py", "content": "private-source"}]),
    payload(files=[{"filename": "main.py", "content": "x" * (MAX_FILE_BYTES + 1)}]),
    payload(evaluation_scope={"scoped_files": ["missing.py"]}),
    payload(files=[{"filename": "main.py", "content": "pass", "changed_lines": [2]}]),
])
async def test_invalid_payload_has_safe_errors_and_creates_no_job(test_client, invalid):
    response = await test_client.post("/api/v1/submissions", json=invalid)
    assert response.status_code == 422, response.text
    assert all({"path", "code", "message"} == set(error) for error in response.json()["detail"])
    assert "private-source" not in response.text
    assert (await test_client.get("/api/v1/submissions")).json() == []


@pytest.mark.asyncio
async def test_request_limit_before_body_parsing_or_job_acceptance(test_client):
    response = await test_client.post("/api/v1/submissions", content=b"{}",
                                      headers={"Content-Length": str(MAX_REQUEST_BYTES + 1)})
    assert response.status_code == 413
    assert response.json()["detail"][0]["code"] == "REQUEST_TOO_LARGE"
    assert (await test_client.get("/api/v1/submissions")).json() == []


@pytest.mark.asyncio
@pytest.mark.parametrize("extra, expected", [(0, 204), (1, 413)])
async def test_body_limit_counts_streamed_bytes_without_length_header(extra, expected):
    received = []

    async def accepted(scope, receive, send):
        received.append(len((await receive())["body"]))
        await send({"type": "http.response.start", "status": 204, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    chunks = [{"type": "http.request", "body": b"a" * MAX_FILE_BYTES, "more_body": True}
              for _ in range(MAX_REQUEST_BYTES // MAX_FILE_BYTES)]
    chunks.append({"type": "http.request", "body": b"a" * extra, "more_body": False})
    receive, send = AsyncMock(side_effect=chunks), AsyncMock()
    await RequestBodyLimitMiddleware(accepted)(
        {"type": "http", "method": "POST", "headers": []}, receive, send)
    assert send.call_args_list[0].args[0]["status"] == expected
    assert received == ([MAX_REQUEST_BYTES] if not extra else [])


@pytest.mark.asyncio
async def test_json_encoding_and_compression_fail_explicitly(test_client):
    for body, headers, status in (
        (b"\xff", {"Content-Type": "application/json"}, 422),
        ('{"files": []}'.encode("utf-16"), {}, 422),
        ('{"files": []}'.encode("utf-16-le"), {}, 422),
        ('{"files": []}'.encode("utf-32-le"), {"Content-Type": "application/problem+json"}, 422),
        (b"gzip", {"Content-Encoding": "gzip"}, 415),
    ):
        response = await test_client.post("/api/v1/submissions", content=body, headers=headers)
        assert response.status_code == status


@pytest.mark.asyncio
@pytest.mark.parametrize("changed_lines", [None, [], [1]])
async def test_source_scope_and_metadata_round_trip(test_client, application, changed_lines):
    """Read the persisted accepted source through authenticated details and hydration."""
    from tests.web.test_contracts_v1 import create
    from web.service.grading_service import GradingRequest
    from web.database.models.submission import Submission

    await create(test_client)
    content = "# café\r\npass\r\n"
    file = {"filename": "src/main.py", "content": content, "file_metadata": {"review": "opaque"}}
    if changed_lines is not None:
        file["changed_lines"] = changed_lines
    source = payload(files=[file, {"filename": "README.md", "content": "Context\n"}],
                     locale="pt-br", metadata={"audit": "host-only"},
                     evaluation_scope={"scoped_files": ["src/main.py"]})
    accepted = await test_client.post("/api/v1/submissions", json=source)
    assert accepted.status_code == 202, accepted.text
    endpoint = accepted.headers["Location"]
    poll = (await test_client.get(endpoint)).json()
    for omitted in ("submission_files", "submission_metadata", "evaluation_scope", "locale"):
        assert omitted not in poll
    assert (await test_client.get(endpoint + "/details")).status_code == 401
    detail = (await test_client.get(endpoint + "/details",
                                    headers={"Authorization": "Bearer input-test-token"})).json()
    assert detail["submission_files"]["src/main.py"] == {**file, "changed_lines": changed_lines}
    assert detail["locale"] == "pt-br"
    assert detail["evaluation_scope"] == source["evaluation_scope"]
    assert detail["submission_metadata"] == source["metadata"]
    async with application.state.host.sessions() as session:
        row = await session.get(Submission, poll["id"])
        bound = GradingRequest.from_row(row)
        assert bound.submission_files["src/main.py"]["content"] == content
        assert bound.submission_files["src/main.py"]["changed_lines"] == changed_lines
        assert bound.locale == "pt-br"
        assert bound.evaluation_scope == source["evaluation_scope"]
