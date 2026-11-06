from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from autograder.models.dataclass.asset import ResolvedAsset
from sandbox_manager.sandbox_container import STAGE, SandboxContainer
from tests.docker_exec_double import StdinExecApi


def _sandbox():
    container_ref = MagicMock()
    container_ref.client = SimpleNamespace(api=StdinExecApi())
    return SandboxContainer(MagicMock(), container_ref), container_ref.client.api


class TestAssetInjection:
    """Test sandbox placement of already retrieved fixture bytes."""

    def test_a_fixture_set_is_one_transfer_as_root(self):
        sandbox, api = _sandbox()
        binary = bytes(range(256)) * 1024
        sandbox.inject_assets([
            ResolvedAsset(target="/tmp/data.csv", content=b"rawcontent", read_only=True),
            ResolvedAsset(target="/tmp/app/nested/blob.bin", content=binary, read_only=False),
            ResolvedAsset(target="relative/empty", content=b"", read_only=True),
            ResolvedAsset(target="/etc/rerooted", content=b"r", read_only=True),  # placed under /tmp
        ])
        # One fixed argv, no shell: paths and bytes travel only inside the archive.
        assert api.calls == [(STAGE, "root", "/")]
        assert api.archives() == [{"tmp/data.csv": (b"rawcontent", 0o444),
                                   "tmp/app/nested/blob.bin": (binary, 0o644),
                                   "tmp/relative/empty": (b"", 0o444),
                                   "tmp/etc/rerooted": (b"r", 0o444)}]

    @pytest.mark.parametrize("target", ["/tmp/../etc/passwd", "/tmp/a/../../etc/passwd", "/tmp/."])
    def test_targets_outside_tmp_are_rejected_before_any_transfer(self, target):
        sandbox, api = _sandbox()
        with pytest.raises(ValueError):
            sandbox.inject_assets([ResolvedAsset(target="/tmp/ok", content=b"x"),
                                   ResolvedAsset(target=target, content=b"x")])
        assert api.calls == []
