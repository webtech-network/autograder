import pytest
from unittest.mock import MagicMock, patch
from autograder.models.config.setup import SetupConfig, AssetConfig
from autograder.services.assets.resolver import AssetSourceResolver
from autograder.models.dataclass.asset import ResolvedAsset
from sandbox_manager.sandbox_container import SandboxContainer

class TestAssetInjection:
    """Test asset resolution and injection logic."""

    def test_setup_config_parsing(self):
        """Test parsing of assets in SetupConfig."""
        data = {
            "assets": [
                {
                    "source": "datasets/data.csv",
                    "target": "/tmp/data.csv",
                    "read_only": True
                }
            ],
            "python": {
                "required_files": ["main.py"]
            }
        }
        
        config = SetupConfig.from_dict(data)
        assert len(config.assets) == 1
        assert config.assets[0].source == "datasets/data.csv"
        assert config.assets[0].target == "/tmp/data.csv"
        assert config.assets[0].read_only is True
        assert config.python.required_files == ["main.py"]

    def test_invalid_asset_target(self):
        """Test validation of absolute target path."""
        with pytest.raises(Exception):
            AssetConfig(source="s", target="relative/path")

    def test_asset_path_traversal(self):
        """Test rejection of path traversal in source."""
        with pytest.raises(Exception):
            AssetConfig(source="../secret", target="/tmp/s")

    @patch('autograder.services.assets.resolver.S3AssetProvider')
    def test_asset_resolver(self, mock_s3_provider_cls):
        """Test AssetSourceResolver orchestration."""
        mock_s3_provider = mock_s3_provider_cls.return_value
        mock_s3_provider.get_asset_tar.return_value = b"tarcontent"
        
        resolver = AssetSourceResolver()
        assets_config = [
            AssetConfig(source="src", target="/tmp/dst")
        ]
        
        resolved = resolver.resolve_assets(assets_config)
        
        assert len(resolved) == 1
        assert isinstance(resolved[0], ResolvedAsset)
        assert resolved[0].target == "/tmp/dst"
        assert resolved[0].tar_content == b"tarcontent"
        
        mock_s3_provider.get_asset_tar.assert_called_once_with("src", "/tmp/dst", True)

    def test_sandbox_inject_assets(self):
        """Test SandboxContainer.inject_assets call to Docker SDK."""
        container_ref = MagicMock()
        sandbox = SandboxContainer(MagicMock(), container_ref)
        
        resolved_assets = [
            ResolvedAsset(target="/tmp/data.csv", tar_content=b"tarcontent")
        ]
        
        sandbox.inject_assets(resolved_assets)
        
        # Check if mkdir -p was called for parent dir
        container_ref.exec_run.assert_any_call(
            cmd="mkdir -p /tmp",
            user="root"
        )
        
        # Check if put_archive was called
        container_ref.put_archive.assert_called_once_with(
            path='/',
            data=b"tarcontent"
        )
