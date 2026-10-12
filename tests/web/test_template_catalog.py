"""Typed HTTP catalog is the Python catalog, without host/provider probes."""
import json
from pathlib import Path

import pytest

from autograder import describe_templates
from autograder.models.contracts.catalog import TemplateCatalog, TemplateDescription


@pytest.mark.asyncio
async def test_catalog_and_detail_publish_the_real_typed_contract(test_client):
    response = await test_client.get("/api/v1/templates")
    assert response.status_code == 200
    catalog = TemplateCatalog.model_validate(response.json())
    assert catalog == describe_templates()
    for template in catalog.templates:
        detail = await test_client.get(f"/api/v1/templates/{template.identifier}")
        assert detail.status_code == 200
        assert TemplateDescription.model_validate(detail.json()) == template
    assert (await test_client.get("/api/v1/templates/uploaded_plugin")).status_code == 404


@pytest.mark.asyncio
@pytest.mark.parametrize("endpoint", ["/api/v1/templates", "/api/v1/templates/webdev"])
async def test_uninitialized_catalog_is_503(test_client, application, endpoint):
    application.state.host.templates = None
    assert (await test_client.get(endpoint)).status_code == 503


def test_openapi_gives_typed_template_and_evaluator_models():
    from web.main import app

    schema = app.openapi()
    snapshot = Path(__file__).resolve().parents[2] / "docs/contracts/v1/openapi.json"
    assert json.loads(snapshot.read_text()) == schema
    for path, model in [("/api/v1/templates", "TemplateCatalog"),
                        ("/api/v1/templates/{template_name}", "TemplateDescription")]:
        response = schema["paths"][path]["get"]["responses"]["200"]["content"]["application/json"]["schema"]
        assert response["$ref"].endswith("/" + model)
    evaluator = schema["components"]["schemas"]["EvaluatorDescription"]
    assert set(evaluator["required"]) >= {"identifier", "parameters_schema", "sample_parameters", "required_capabilities"}
    assert evaluator["properties"]["required_capabilities"]["items"]["enum"] == [
        "sandbox_execution", "http_network", "ai_provider", "structural_analysis"]
