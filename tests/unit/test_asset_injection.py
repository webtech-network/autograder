from unittest.mock import MagicMock
from autograder.models.dataclass.asset import ResolvedAsset
from sandbox_manager.sandbox_container import SandboxContainer

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
        
        # Check if mkdir -p was called for parent dir
        container_ref.exec_run.assert_any_call(
            cmd=["mkdir", "-p", "/tmp"],
            user="root"
        )

        # Check if Base64 write command was called
        call_args = container_ref.exec_run.call_args_list
        found_b64_call = False
        for call in call_args:
            cmd = call.kwargs.get("cmd")
            if isinstance(cmd, list) and len(cmd) == 3 and "cmF3Y29udGVudA==" in cmd[2]:
                found_b64_call = True
                break
        assert found_b64_call, "Base64 write call not found in exec_run calls"
