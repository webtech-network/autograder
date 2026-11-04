"""The HTTP host accepts exactly the core locale set, through the real application."""
import pytest

from autograder.models.locale import LOCALE_IDS
from tests.locale_cases import ACCEPTED, REJECTED
from tests.web.test_contracts_v1 import HEADERS, create


@pytest.fixture(autouse=True)
def integration_auth(monkeypatch):
    monkeypatch.setenv("AUTOGRADER_INTEGRATION_TOKEN", "test-contract-token")


def payload(**updates):
    value = {"external_assignment_id": "assignment", "external_user_id": "student",
             "username": "Student", "files": [{"filename": "main.py", "content": "print('Hello')\n"}]}
    value.update(updates)
    return value


@pytest.mark.parametrize("locale", REJECTED + [None, 1, ["en"]])
async def test_unsupported_locale_is_a_422_before_acceptance(test_client, locale):
    await create(test_client)
    response = await test_client.post("/api/v1/submissions", json=payload(locale=locale))
    assert response.status_code == 422, response.text
    assert [error["path"] for error in response.json()["detail"]] == [["body", "locale"]]
    history = await test_client.get("/api/v1/submissions/user/student", headers=HEADERS)
    assert history.status_code == 200 and history.json() == []


@pytest.mark.parametrize(("locale", "canonical"), ACCEPTED)
async def test_supported_locale_is_bound_in_canonical_form(test_client, locale, canonical):
    await create(test_client)
    accepted = await test_client.post("/api/v1/submissions", json=payload(locale=locale))
    assert accepted.status_code == 202, accepted.text
    detail = await test_client.get(accepted.headers["Location"] + "/details", headers=HEADERS)
    assert detail.json()["locale"] == canonical


async def test_omitted_locale_defaults_to_english(test_client):
    await create(test_client)
    accepted = await test_client.post("/api/v1/submissions", json=payload())
    detail = await test_client.get(accepted.headers["Location"] + "/details", headers=HEADERS)
    assert detail.json()["locale"] == "en"


def test_openapi_publishes_the_core_locale_set(application):
    schema = application.openapi()["components"]["schemas"]
    assert schema["SubmissionCreate"]["properties"]["locale"]["enum"] == list(LOCALE_IDS)
