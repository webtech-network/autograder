"""The typed fixture contract reaches the concrete Docker staging adapter."""
from unittest.mock import Mock

from autograder import build_pipeline
from autograder.models.capabilities import HostCapabilities
from execution_host.docker import DockerSession
from sandbox_manager.models.sandbox_models import Language
from tests.unit.pipeline.test_host_capabilities import definition, submission


def test_typed_fixture_maps_to_host_root_and_closes_owned_session():
    manager = Mock()
    concrete = manager.get_sandbox.return_value
    session = DockerSession(manager, Language.PYTHON)
    resolver = Mock(return_value=b"asset bytes")
    pipeline = build_pipeline(definition=definition(preparation={"fixtures": [
        {"reference": "datasets/data.csv", "path": "data.csv", "read_only": True}]}),
        capabilities=HostCapabilities(execution=lambda language: session, fixtures=resolver))
    assert pipeline.run(submission()).outcome.status == "completed"
    resolver.assert_called_once_with("datasets/data.csv")
    assets = concrete.inject_assets.call_args.args[0]
    assert len(assets) == 1
    assert assets[0].target == "/tmp/app/data.csv"
    assert assets[0].content == b"asset bytes" and assets[0].read_only is True
    manager.destroy_sandbox.assert_called_once_with(Language.PYTHON, concrete)
