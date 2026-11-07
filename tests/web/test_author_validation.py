"""The Author page's "test your rubric" step is what the HTTP API answers (ONB-05, #431).

The Author page tells teachers to check a definition with
``POST /api/v1/configs/validate`` before they publish it. Every tutorial
definition is accepted with its hash, and every rejected fragment on an Author
page receives exactly the response the page shows.
"""
# pylint: disable=missing-function-docstring
import json

import pytest

from autograder import compile_definition
from tests.unit.test_documentation import author_pages, blocks, load, merged


@pytest.mark.asyncio
@pytest.mark.parametrize("assignment", ["python-io", "web-page", "compiled"])
async def test_every_tutorial_definition_validates_over_http(test_client, assignment):
    definition = load(f"examples/tutorial/{assignment}/definition.json")
    response = await test_client.post("/api/v1/configs/validate", json=definition)
    assert response.status_code == 200, response.text
    assert response.json()["definition_hash"] == compile_definition(definition).definition_hash


@pytest.mark.asyncio
async def test_rejected_fragments_get_the_response_the_page_shows(test_client):
    checked = 0
    for page in author_pages():
        rejected = None
        for language, body, kind, argument in blocks(page):
            if language != "json":
                continue
            if kind == "rejected":
                rejected = merged(load(argument), json.loads(body))
            elif kind == "validate-response":
                response = await test_client.post("/api/v1/configs/validate", json=rejected)
                assert response.status_code == 422, (page, response.text)
                assert response.json() == json.loads(body), page
                checked += 1
    assert checked >= 1
