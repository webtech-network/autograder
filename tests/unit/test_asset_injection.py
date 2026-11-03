import pytest
from unittest.mock import MagicMock, patch
from execution_host.assets.config import AssetConfig
from execution_host.assets.resolver import AssetSourceResolver
from autograder.models.dataclass.asset import ResolvedAsset
from sandbox_manager.sandbox_container import WRITE, SandboxContainer

class TestAssetInjection:
    """Test asset resolution and injection logic."""

    def test_invalid_asset_target(self):
        """Test validation of absolute target path."""
        with pytest.raises(Exception):
            AssetConfig(source="s", target="relative/path")

    def test_asset_path_traversal(self):
        """Test rejection of path traversal in source."""
        with pytest.raises(Exception):
            AssetConfig(source="../secret", target="/tmp/s")

    @patch('execution_host.assets.resolver.S3AssetProvider')
    def test_asset_resolver(self, mock_s3_provider_cls):
        """Test AssetSourceResolver orchestration."""
        mock_s3_provider = mock_s3_provider_cls.return_value
        mock_s3_provider.get_asset.return_value = b"rawcontent"
        
        resolver = AssetSourceResolver()
        assets_config = [
            AssetConfig(source="src", target="/tmp/dst")
        ]
        
        resolved = resolver.resolve_assets(assets_config)
        
        assert len(resolved) == 1
        assert isinstance(resolved[0], ResolvedAsset)
        assert resolved[0].target == "/tmp/dst"
        assert resolved[0].content == b"rawcontent"
        
        mock_s3_provider.get_asset.assert_called_once_with("src", "/tmp/dst", True)

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
