from unittest.mock import MagicMock
from autograder.models.dataclass.asset import ResolvedAsset
from sandbox_manager.sandbox_container import WRITE, SandboxContainer

class TestAssetInjection:
    """Test sandbox placement of already retrieved fixture bytes."""

    def test_sandbox_inject_assets(self):
        """Test SandboxContainer.inject_assets with shell-escaped Base64 injection."""
        container_ref = MagicMock()
        # Mock success response
        mock_res = MagicMock()
        mock_res.exit_code = 0
        container_ref.exec_run.return_value = mock_res
        
        sandbox = SandboxContainer(MagicMock(), container_ref)
        
        resolved_assets = [
            ResolvedAsset(target="/tmp/data.csv", content=b"rawcontent", read_only=True)
        ]
        
        sandbox.inject_assets(resolved_assets)
        
        commands = [(call.kwargs["cmd"], call.kwargs["user"]) for call in container_ref.exec_run.call_args_list]
        assert (["mkdir", "-p", "/tmp"], "root") in commands
        writes = [cmd for cmd, user in commands if cmd[:3] == ["/bin/sh", "-c", WRITE] and user == "root"]
        # The target and the base64 content are positional parameters, never shell text.
        assert [(cmd[4], cmd[5], cmd[6]) for cmd in writes] == [("/tmp/data.csv", "new", "cmF3Y29udGVudA==")]
        assert (["chmod", "444", "/tmp/data.csv"], "root") in commands
