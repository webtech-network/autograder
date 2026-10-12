"""Host construction isolates settings, sessions, workers and resource lifetimes."""
import asyncio
from dataclasses import replace
from unittest.mock import Mock

import pytest
from httpx import AsyncClient, ASGITransport

from autograder.models.capabilities import HostCapabilities
from web.core.config import Settings
from web.main import create_app


def test_settings_read_environment_at_construction(monkeypatch):
    monkeypatch.setenv("APP_ENV", "first")
    first = Settings()
    monkeypatch.setenv("APP_ENV", "second")
    second = Settings()
    assert first.APP_ENV == "first" and second.APP_ENV == "second"
    assert first.CORS_ORIGINS == ["*"]
    assert first.CORS_ORIGINS is not second.CORS_ORIGINS


@pytest.mark.parametrize("values", [{"WORKER_COUNT": 0}, {"MAX_ATTEMPTS": 0}, {"LEASE_SECONDS": 0}, {"DATABASE_URL": ""}])
def test_invalid_host_configuration_fails_early(values):
    with pytest.raises(ValueError):
        Settings(**values)


@pytest.mark.asyncio
async def test_application_instances_have_isolated_dependencies(session_factory, tmp_path):
    owners = [Mock(), Mock()]
    first = create_app(Settings(INTEGRATION_TOKEN="first", RECEIPT_DIR=str(tmp_path / "first")),
                       session_factory=session_factory, capabilities=HostCapabilities(),
                       resource_owner=owners[0], start_workers=False)
    second = create_app(Settings(INTEGRATION_TOKEN="second", RECEIPT_DIR=str(tmp_path / "second")),
                        session_factory=Mock(), capabilities=HostCapabilities(),
                        resource_owner=owners[1], start_workers=False)
    assert first.state.host.sessions is not second.state.host.sessions
    assert first.state.host.worker.tasks is not second.state.host.worker.tasks
    assert first.state.host.worker.stopping is not second.state.host.worker.stopping
    assert first.state.host.capabilities is not second.state.host.capabilities
    assert first.state.host.resource_owner is not second.state.host.resource_owner
    async with first.router.lifespan_context(first):
        async with AsyncClient(transport=ASGITransport(app=first), base_url="http://test") as client:
            response = await client.get("/api/v1/configs/id/1", headers={"Authorization": "Bearer second"})
            assert response.status_code == 401
            assert (await client.get("/api/v1/ready")).json()["durable_acceptance"] is True
    owners[0].close.assert_called_once()
    owners[1].close.assert_not_called()


@pytest.mark.asyncio
async def test_shutdown_drains_owned_execution_before_closing_resources(application):
    host = application.state.host
    running, release = asyncio.Event(), asyncio.Event()
    owner = Mock()
    host.resource_owner = owner

    async def ongoing():
        running.set()
        await release.wait()
        owner.close.assert_not_called()

    task = asyncio.create_task(ongoing())
    host.worker.tasks.add(task)
    await running.wait()
    closing = asyncio.create_task(host.close())
    await asyncio.sleep(0)
    assert not closing.done() and host.worker.stopping.is_set()
    owner.close.assert_not_called()
    release.set()
    await closing
    owner.close.assert_called_once()
    host.resource_owner = None
