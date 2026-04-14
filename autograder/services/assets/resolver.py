import os
import logging
from typing import List, Optional
from autograder.services.assets.s3_provider import S3AssetProvider
from autograder.services.assets.cache_manager import AssetCacheManager
from autograder.models.config.setup import AssetConfig
from autograder.models.dataclass.asset import ResolvedAsset

logger = logging.getLogger("AssetSourceResolver")

class AssetSourceResolver:
    def __init__(self):
        in_memory_limit = int(os.getenv("CRITERIA_ASSETS_IN_MEMORY_CACHE_LIMIT", "100"))
        self.cache_manager = AssetCacheManager(in_memory_limit=in_memory_limit)
        self.provider = S3AssetProvider(self.cache_manager)
        
    def resolve_assets(self, assets_config: List[AssetConfig]) -> List[ResolvedAsset]:
        """
        Resolve all assets in the configuration.
        
        Args:
            assets_config: List of AssetConfig objects.
            
        Returns:
            List of ResolvedAsset objects.
            If any asset fails to resolve, an exception is raised.
        """
        resolved_assets = []
        
        for asset in assets_config:
            source = asset.source
            target = asset.target
            read_only = asset.read_only
            
            # Resolve asset
            tar_content = self.provider.get_asset_tar(source, target, read_only)
            
            if not tar_content:
                raise RuntimeError(f"Failed to resolve asset: source={source}, target={target}")
                
            resolved_assets.append(ResolvedAsset(
                target=target,
                tar_content=tar_content
            ))
            
        return resolved_assets
